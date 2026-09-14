package manager

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"srmc-agent/config"

	"gopkg.in/yaml.v3"
)

// UpdateProgressFunc 上报更新进度回调：step=当前步骤, status=running/success/failed, progress=0-100, errMsg=错误信息
type UpdateProgressFunc func(step string, status string, progress int, errMsg string)

// UpdateParams 一次批量更新的执行参数（由 transport 层解析 update 消息后传入）
type UpdateParams struct {
	TaskID     string
	UpdateType string // docker / binary
	FileURL    string
	FileSHA256 string
	FileName   string
	Version    string

	// docker
	ImageName     string
	ImageTag      string
	ContainerName string
	ComposeFile   string

	// binary
	BinaryTargetPath   string
	BinaryServiceName  string
	BackupBeforeUpdate bool
	AutoStopOld        bool
	AutoStartAfter     bool

	// 可选同步配置文件（前端批量更新弹窗上传）
	ComposeFileContent string // docker-compose.yml 内容
	ConfigFileContent  string // config.yaml 内容
	ServiceFileContent string // srmc-agent.service 内容（仅二进制模式）
}

// PendingFile 写在宿主机 updates/pending.json，供新 Agent 启动接力。
type PendingFile struct {
	TaskID      string `json:"task_id"`
	Version     string `json:"version"`
	ComposeFile string `json:"compose_file"`
	TarPath     string `json:"tar_path"`
	ImageID     string `json:"image_id"`
	CreatedAt   int64  `json:"created_at"`
}

// pending 接力相关常量
const (
	pendingFileName = "pending.json"
)

// pendingFilePath 返回宿主机 pending.json 路径。
func pendingFilePath() string {
	return filepath.Join(config.GlobalConfig.Deploy.UpdatesDir, pendingFileName)
}

// ExecuteUpdate 执行一次更新任务，通过 report 回调分步上报进度。
func ExecuteUpdate(p UpdateParams, report UpdateProgressFunc) {
	tmpDir := filepath.Join(os.TempDir(), "srmc-agent-updates", p.TaskID)
	if err := os.MkdirAll(tmpDir, 0755); err != nil {
		report("初始化临时目录", "failed", 0, err.Error())
		return
	}
	defer os.RemoveAll(tmpDir)

	// 1. 下载文件
	report("下载更新文件", "running", 5, "")
	name := p.FileName
	if name == "" {
		name = "update.bin"
	}
	localPath := filepath.Join(tmpDir, name)
	if err := downloadFile(p.FileURL, localPath); err != nil {
		report("下载文件", "failed", 5, err.Error())
		return
	}

	// 2. SHA256 校验
	report("校验 SHA256", "running", 15, "")
	sum, err := fileSHA256(localPath)
	if err != nil {
		report("SHA256 计算失败", "failed", 15, err.Error())
		return
	}
	if p.FileSHA256 != "" && !strings.EqualFold(sum, p.FileSHA256) {
		report("SHA256 校验失败", "failed", 15,
			fmt.Sprintf("校验不一致：期望 %s，实际 %s，已中止更新", p.FileSHA256, sum))
		return
	}

	// 3. 按类型执行
	if p.UpdateType == "docker" {
		executeDockerUpdate(localPath, p, report)
	} else {
		executeBinaryUpdate(localPath, p, report)
	}
}

// executeDockerUpdate：load 镜像 → 存 tar 到 updates_dir → 写 pending.json → nsenter nohup 触发 compose 重启 → 上报 95% 后 Agent 进程自行结束
// compose down 会杀掉当前容器，compose up 由宿主机后台进程继续执行，新 Agent 启动后读 pending.json 接力。
func executeDockerUpdate(localPath string, p UpdateParams, report UpdateProgressFunc) {
	composeFile := p.ComposeFile
	if composeFile == "" {
		composeFile = config.GlobalConfig.Deploy.ComposeFile
	}

	// 1. docker load
	report("docker load 载入镜像", "running", 20, "")
	out, err := runDockerCmd([]string{"docker", "load", "-i", localPath})
	if err != nil {
		report("docker load 失败", "failed", 20, string(out))
		return
	}
	log.Printf("[UPDATE] docker load done: %s", string(out))

	newImageID := parseNewImageID(string(out))

	// 2. 把 tar 存到 updates_dir（宿主机路径，compose up 后新 Agent 能读到）
	updatesDir := config.GlobalConfig.Deploy.UpdatesDir
	tarOnHost := filepath.Join(updatesDir, p.TaskID+".tar")
	report("保存 tar 到宿主机", "running", 30, "")
	if !isRunningInContainer() {
		if err := copyFile(localPath, tarOnHost); err != nil {
			report("保存 tar 失败", "failed", 30, err.Error())
			return
		}
	} else {
		if err := writeLocalToHost(localPath, tarOnHost); err != nil {
			report("保存 tar 到宿主机失败", "failed", 30, err.Error())
			return
		}
	}

	// 3. 可选：同步 compose.yml / config.yaml 到宿主机
	if p.ComposeFileContent != "" {
		report("同步 docker-compose.yml", "running", 42, "")
		if err := writeContentToHost(p.ComposeFileContent, composeFile); err != nil {
			log.Printf("[UPDATE] write compose.yml: %v", err)
		}
	}
	if p.ConfigFileContent != "" {
		report("同步 config.yaml", "running", 45, "")
		// 合并保护字段（server.url/token, agent.uuid/name/ip, deploy.deploy_dir）
		merged, err := mergeConfigOnHost(p.ConfigFileContent)
		if err != nil {
			log.Printf("[UPDATE] merge config: %v (仍尝试写入)", err)
			merged = p.ConfigFileContent
		}
		configPath := filepath.Join(config.GlobalConfig.Deploy.DeployDir, "config.yaml")
		if err := writeContentToHost(merged, configPath); err != nil {
			log.Printf("[UPDATE] write config.yaml: %v", err)
		}
	}

	// 4. 写 pending.json（宿主机上）
	report("写入 pending.json", "running", 50, "")
	pending := PendingFile{
		TaskID:      p.TaskID,
		Version:     p.Version,
		ComposeFile: composeFile,
		TarPath:     tarOnHost,
		ImageID:     newImageID,
		CreatedAt:   time.Now().Unix(),
	}
	if err := writePendingHost(pending); err != nil {
		report("写入 pending.json 失败", "failed", 40, err.Error())
		return
	}

	// 4. nsenter 宿主机后台执行 compose down && up -d
	if composeFile != "" {
		report("触发宿主机 compose 重启", "running", 85, "")
		if !fileExistsHost(composeFile) {
			report("compose 文件不存在", "failed", 85, fmt.Sprintf("compose 文件不存在: %s", composeFile))
			return
		}
		if err := triggerHostCompose(composeFile); err != nil {
			log.Printf("[UPDATE] triggerHostCompose error (继续): %v", err)
			// 不 return：即使 nohup 触发失败，新 Agent 读 pending 也可以自己执行 compose
		}
	}

	// 5. 上报 95%，Agent 进程将随 compose down 自行结束
	report("等待容器重启", "running", 95, "Agent 容器即将重建，新 Agent 启动后接力上报成功")

	// 进程不退出，让 main.go 的主循环继续等 compose down 杀掉我们
	// 如果不在容器里（binary 模式跑 docker），手动执行 compose
	if !isRunningInContainer() && composeFile != "" {
		workDir := filepath.Dir(composeFile)
		_, _ = runComposeCmd(composeFile, workDir, "down")
		out2, err2 := runComposeCmd(composeFile, workDir, "up", "-d")
		if err2 != nil {
			report("compose up 失败", "failed", 95, string(out2))
			return
		}
		report("镜像更新完成", "success", 100, "")
		// 清理 updates 里的 tar 和 pending
		cleanupDockerSuccess(pending)
		// 旧镜像轮转
		cleanOldDockerImages(composeFile, 2)
	}
}

// triggerHostCompose 通过 nsenter 在宿主机后台 nohup 执行 compose down && up -d。
// 用 nohup + & 让它脱离 Agent 容器的进程组，compose down 杀掉容器后 up 还能继续。
func triggerHostCompose(composeFile string) error {
	workDir := filepath.Dir(composeFile)
	shell := getShellPath()
	cmdText := fmt.Sprintf(
		"cd %s && (docker compose -f %s down 2>/dev/null || docker-compose -f %s down 2>/dev/null); "+
			"docker rm -f srmc-agent 2>/dev/null; "+
			"(docker compose -f %s up -d 2>/dev/null || docker-compose -f %s up -d 2>/dev/null); "+
			"sleep 1; rm -f %s",
		shellQuote(workDir), shellQuote(composeFile), shellQuote(composeFile),
		shellQuote(composeFile), shellQuote(composeFile),
		shellQuote(pendingFilePath()),
	)

	if isRunningInContainer() {
		// nsenter 宿主机 + nohup + & 脱离容器
		cmd := exec.Command("nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "--",
			shell, "-c", "nohup "+cmdText+" >/dev/null 2>&1 &")
		return cmd.Start()
	}
	// 宿主机直接 nohup 后台执行
	cmd := exec.Command(shell, "-c", "nohup "+cmdText+" >/dev/null 2>&1 &")
	return cmd.Start()
}

// writePendingHost 写 pending.json 到宿主机。
func writePendingHost(pending PendingFile) error {
	data, err := json.MarshalIndent(pending, "", "  ")
	if err != nil {
		return err
	}
	path := pendingFilePath()
	if !isRunningInContainer() {
		return os.WriteFile(path, data, 0644)
	}
	out, err := runHostCommand(getShellPath(), fmt.Sprintf("cat > %s <<'PENDEND_JSON'\n%s\nPENDEND_JSON\n", shellQuote(path), string(data)))
	_ = out
	return err
}

// readPendingHost 读宿主机上的 pending.json，不存在返回 nil, nil。
func readPendingHost() (*PendingFile, error) {
	path := pendingFilePath()
	var content []byte
	var err error
	if !isRunningInContainer() {
		content, err = os.ReadFile(path)
	} else {
		out, runErr := runHostCommand(getShellPath(), fmt.Sprintf("cat %s 2>/dev/null || true", shellQuote(path)))
		if runErr == nil {
			content = []byte(out)
		}
	}
	if err != nil || len(content) == 0 {
		return nil, nil
	}
	var p PendingFile
	if err := json.Unmarshal(content, &p); err != nil {
		return nil, err
	}
	return &p, nil
}

// removePendingHost 删宿主机 pending.json。
func removePendingHost() {
	path := pendingFilePath()
	if !isRunningInContainer() {
		os.Remove(path)
	} else {
		runHostCommand(getShellPath(), fmt.Sprintf("rm -f %s", shellQuote(path)))
	}
}

// CheckPendingUpdate 启动时调用：检查 pending.json，如果存在且 compose 还没 up 则补执行 compose up。
// 返回 pending 指针供 main.go 后续接力上报使用。
func CheckPendingUpdate() *PendingFile {
	pending, err := readPendingHost()
	if err != nil || pending == nil {
		return nil
	}
	// 检查 compose 状态：如果没有 running 的 srmc-agent 容器，补执行 compose up
	if pending.ComposeFile != "" {
		workDir := filepath.Dir(pending.ComposeFile)
		out, err := runDockerCmd([]string{"docker", "ps", "--filter", "name=srmc-agent", "--format", "{{.Names}}"})
		if err != nil || len(strings.TrimSpace(string(out))) == 0 {
			log.Printf("[PENDING] compose not up yet, executing compose up for %s", pending.ComposeFile)
			runComposeCmd(pending.ComposeFile, workDir, "up", "-d")
		}
	}
	return pending
}

// CheckPendingUpdateSilent 静默检查（不执行 compose）。
func CheckPendingUpdateSilent() *PendingFile {
	p, _ := readPendingHost()
	return p
}

// RemovePendingFile 删 pending.json + updates/*.tar。
func RemovePendingFile() {
	pending, _ := readPendingHost()
	removePendingHost()
	if pending != nil && pending.TarPath != "" {
		if !isRunningInContainer() {
			os.Remove(pending.TarPath)
		} else {
			runHostCommand(getShellPath(), fmt.Sprintf("rm -f %s", shellQuote(pending.TarPath)))
		}
	}
}

// ReportPendingSuccess 接力上报 update_progress success（由 transport 层调用）。
func ReportPendingSuccess(taskID, version string) {
	log.Printf("[PENDING] ReportPendingSuccess for task=%s version=%s", taskID, version)
}

// parseNewImageID 从 docker load 输出解析新镜像名（Loaded image: xxx:tag）。
func parseNewImageID(output string) string {
	for _, line := range strings.Split(output, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "Loaded image:") {
			return strings.TrimPrefix(line, "Loaded image:")
		}
		if strings.HasPrefix(line, "Loaded image ID:") {
			return strings.TrimPrefix(line, "Loaded image ID:")
		}
	}
	return ""
}

// cleanupDockerSuccess 新 Agent 接力成功后清理 tar 和 pending。
func cleanupDockerSuccess(p PendingFile) {
	removePendingHost()
	if p.TarPath != "" {
		if !isRunningInContainer() {
			os.Remove(p.TarPath)
		} else {
			runHostCommand(getShellPath(), fmt.Sprintf("rm -f %s", shellQuote(p.TarPath)))
		}
	}
}

// cleanOldDockerImages 新容器起来后，删除旧镜像（保留最近 keep 代）。
// 通过 compose 文件里的 image: 字段定位镜像名，然后按创建时间排序 rmi 最旧的。
func cleanOldDockerImages(composeFile string, keep int) {
	if keep <= 0 {
		return
	}
	imageName := extractImageFromCompose(composeFile)
	if imageName == "" {
		log.Printf("[UPDATE] cleanOldDockerImages: cannot extract image name from compose")
		return
	}
	out, err := runDockerCmd([]string{"docker", "images", "--format", "{{.Repository}}:{{.Tag}}", imageName})
	if err != nil {
		log.Printf("[UPDATE] cleanOldDockerImages docker images failed: %v", err)
		return
	}
	lines := strings.Split(strings.TrimSpace(string(out)), "\n")
	var images []string
	for _, l := range lines {
		l = strings.TrimSpace(l)
		if l != "" {
			images = append(images, l)
		}
	}
	// 去掉 <none> 镜像
	var named []string
	for _, img := range images {
		if !strings.Contains(img, "<none>") {
			named = append(named, img)
		}
	}
	if len(named) <= keep {
		return
	}
	toRemove := named[:len(named)-keep]
	for _, img := range toRemove {
		if _, err := runDockerCmd([]string{"docker", "rmi", img}); err != nil {
			log.Printf("[UPDATE] rmi old image %s failed: %v", img, err)
		} else {
			log.Printf("[UPDATE] cleaned old image: %s", img)
		}
	}
}

// extractImageFromCompose 从 compose 文件里读 image: 字段值。
func extractImageFromCompose(composeFile string) string {
	var content string
	if !isRunningInContainer() {
		data, err := os.ReadFile(composeFile)
		if err != nil {
			return ""
		}
		content = string(data)
	} else {
		out, err := runHostCommand(getShellPath(), fmt.Sprintf("cat %s", shellQuote(composeFile)))
		if err != nil {
			return ""
		}
		content = out
	}
	for _, line := range strings.Split(content, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "image:") {
			val := strings.TrimSpace(strings.TrimPrefix(line, "image:"))
			val = strings.Trim(val, "\"'")
			return val
		}
	}
	return ""
}

// fileExistsHost 判断宿主机路径是否存在。
func fileExistsHost(path string) bool {
	if !isRunningInContainer() {
		_, err := os.Stat(path)
		return err == nil
	}
	out, err := runHostCommand(getShellPath(), fmt.Sprintf("test -f %s && echo ok", shellQuote(path)))
	return err == nil && strings.TrimSpace(out) == "ok"
}

// executeBinaryUpdate 更新二进制：备份 → 停止 → 替换(保留权限) → 启动 → 检查，失败自动回滚。
func executeBinaryUpdate(binPath string, p UpdateParams, report UpdateProgressFunc) {
	target := p.BinaryTargetPath
	if target == "" {
		target = config.GlobalConfig.Deploy.BinaryPath
	}
	if target == "" {
		report("缺少目标路径", "failed", 30, "未配置二进制目标路径")
		return
	}
	serviceName := p.BinaryServiceName
	if serviceName == "" {
		serviceName = config.GlobalConfig.Deploy.ServiceName
	}

	backupDir := config.GlobalConfig.Deploy.BackupDir

	// 可选：同步 config.yaml / service 文件
	if p.ConfigFileContent != "" {
		report("同步 config.yaml", "running", 42, "")
		merged, err := mergeConfigOnHost(p.ConfigFileContent)
		if err != nil {
			log.Printf("[UPDATE] merge config: %v (仍尝试写入)", err)
			merged = p.ConfigFileContent
		}
		configPath := filepath.Join(config.GlobalConfig.Deploy.DeployDir, "config.yaml")
		if err := writeContentToHost(merged, configPath); err != nil {
			log.Printf("[UPDATE] write config.yaml: %v", err)
		}
	}
	if p.ServiceFileContent != "" {
		report("同步 systemd 服务文件", "running", 44, "")
		servicePath := "/etc/systemd/system/" + serviceName + ".service"
		if err := writeContentToHost(p.ServiceFileContent, servicePath); err != nil {
			log.Printf("[UPDATE] write service file: %v", err)
		}
		runHostCommand(getShellPath(), "systemctl daemon-reload")
	}

	// 备份（统一到 backup_dir）
	var backupPath string
	if p.BackupBeforeUpdate {
		report("备份旧文件", "running", 45, "")
		backupPath = filepath.Join(backupDir, filepath.Base(target)+".bak."+time.Now().Format("20060102150405"))
		if err := copyFileHost(target, backupPath); err != nil {
			report("备份旧文件失败", "failed", 45, err.Error())
			return
		}
		keep := config.GlobalConfig.Deploy.BackupKeep
		if keep > 0 {
			cleanOldBackupsDir(backupDir, filepath.Base(target)+".bak.", keep)
		}
	}

	// 停止旧程序
	if p.AutoStopOld && serviceName != "" {
		report("停止旧程序 "+serviceName, "running", 60, "")
		if _, err := runSystemctl("stop", serviceName); err != nil {
			log.Printf("[UPDATE] stop service %s (忽略): %v", serviceName, err)
		}
	}

	oldPerm := os.FileMode(0755)
	if m, err := statPermHost(target); err == nil {
		oldPerm = m
	}

	report("替换文件", "running", 75, "")
	if err := mkdirAllHost(filepath.Dir(target)); err != nil {
		report("创建目标目录失败", "failed", 75, err.Error())
		rollbackBinary(target, backupPath, serviceName, report)
		return
	}
	if err := writeLocalToHost(binPath, target); err != nil {
		report("替换文件失败", "failed", 75, err.Error())
		rollbackBinary(target, backupPath, serviceName, report)
		return
	}
	if err := chmodHost(target, oldPerm); err != nil {
		log.Printf("[UPDATE] chmod %s: %v", target, err)
	}

	if p.AutoStartAfter && serviceName != "" {
		report("启动程序 "+serviceName, "running", 90, "")
		if out, err := runSystemctl("start", serviceName); err != nil {
			report("启动程序失败", "failed", 90, out)
			rollbackBinary(target, backupPath, serviceName, report)
			return
		}
		report("检查运行状态", "running", 95, "")
		if out, err := runSystemctl("is-active", serviceName); err != nil || strings.TrimSpace(out) != "active" {
			report("程序未正常运行", "failed", 95, strings.TrimSpace(out))
			rollbackBinary(target, backupPath, serviceName, report)
			return
		}
	}

	report("二进制更新完成", "success", 100, "")
}

// rollbackBinary 更新失败时恢复备份文件并尝试重启旧程序。
func rollbackBinary(target, backupPath, serviceName string, report UpdateProgressFunc) {
	if backupPath == "" {
		return
	}
	if _, err := statPermHost(backupPath); err == nil {
		if err := copyFileHost(backupPath, target); err == nil {
			report("已回滚旧文件", "failed", 100, "更新失败，已恢复备份文件: "+backupPath)
		}
	}
	if serviceName != "" {
		if _, err := runSystemctl("start", serviceName); err == nil {
			report("已尝试恢复旧程序", "failed", 100, "更新失败，已恢复备份并重启 "+serviceName)
		}
	}
}

// cleanOldBackupsDir 清理 backup_dir 里的旧备份，只保留最近 keep 份。
func cleanOldBackupsDir(backupDir, prefix string, keep int) {
	entries, err := listDirHost(backupDir)
	if err != nil {
		log.Printf("[UPDATE] cleanOldBackupsDir list dir failed: %v", err)
		return
	}
	var backups []string
	for _, name := range entries {
		if strings.HasPrefix(name, prefix) {
			backups = append(backups, name)
		}
	}
	if len(backups) <= keep {
		return
	}
	sort.Strings(backups)
	toDelete := backups[:len(backups)-keep]
	for _, name := range toDelete {
		full := filepath.Join(backupDir, name)
		if err := removeFileHost(full); err != nil {
			log.Printf("[UPDATE] clean backup %s: %v", name, err)
		} else {
			log.Printf("[UPDATE] cleaned old backup: %s", name)
		}
	}
}

// listDirHost 列出宿主机目录下的文件名。
func listDirHost(dir string) ([]string, error) {
	if !isRunningInContainer() {
		entries, err := os.ReadDir(dir)
		if err != nil {
			return nil, err
		}
		var names []string
		for _, e := range entries {
			names = append(names, e.Name())
		}
		return names, nil
	}
	out, err := runHostCommand(getShellPath(), fmt.Sprintf("ls -1 %s", shellQuote(dir)))
	if err != nil {
		return nil, fmt.Errorf("%v: %s", err, strings.TrimSpace(out))
	}
	return strings.Split(strings.TrimSpace(out), "\n"), nil
}

// removeFileHost 删除宿主机文件。
func removeFileHost(path string) error {
	if !isRunningInContainer() {
		return os.Remove(path)
	}
	out, err := runHostCommand(getShellPath(), fmt.Sprintf("rm -f %s", shellQuote(path)))
	if err != nil {
		return fmt.Errorf("%v: %s", err, strings.TrimSpace(out))
	}
	return nil
}

// downloadFile 通过 HTTP 流式下载文件到本地。
func downloadFile(url, dest string) error {
	client := &http.Client{Timeout: 30 * time.Minute}
	resp, err := client.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("下载失败：HTTP %d", resp.StatusCode)
	}
	out, err := os.Create(dest)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, resp.Body)
	return err
}

// fileSHA256 计算文件 SHA256。
func fileSHA256(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// copyFile 复制文件内容。
func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	return out.Sync()
}

// ==================== 宿主机文件操作 ====================

func shellQuote(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'"
}

func copyFileHost(src, dst string) error {
	if !isRunningInContainer() {
		return copyFile(src, dst)
	}
	out, err := runHostCommand(getShellPath(), fmt.Sprintf("cp -p %s %s", shellQuote(src), shellQuote(dst)))
	if err != nil {
		return fmt.Errorf("%v: %s", err, strings.TrimSpace(out))
	}
	return nil
}

func statPermHost(path string) (os.FileMode, error) {
	if !isRunningInContainer() {
		fi, err := os.Stat(path)
		if err != nil {
			return 0, err
		}
		return fi.Mode().Perm(), nil
	}
	out, err := runHostCommand(getShellPath(), fmt.Sprintf("stat -c %%a %s", shellQuote(path)))
	if err != nil {
		return 0, fmt.Errorf("%v: %s", err, strings.TrimSpace(out))
	}
	v := strings.TrimSpace(out)
	mode, err := strconv.ParseUint(v, 8, 32)
	if err != nil {
		return 0, fmt.Errorf("解析权限失败 %q: %v", v, err)
	}
	return os.FileMode(mode), nil
}

func mkdirAllHost(dir string) error {
	if !isRunningInContainer() {
		return os.MkdirAll(dir, 0755)
	}
	out, err := runHostCommand(getShellPath(), fmt.Sprintf("mkdir -p %s", shellQuote(dir)))
	if err != nil {
		return fmt.Errorf("%v: %s", err, strings.TrimSpace(out))
	}
	return nil
}

func writeLocalToHost(srcLocal, dstHost string) error {
	in, err := os.Open(srcLocal)
	if err != nil {
		return err
	}
	defer in.Close()

	if !isRunningInContainer() {
		out, err := os.Create(dstHost)
		if err != nil {
			return err
		}
		defer out.Close()
		if _, err := io.Copy(out, in); err != nil {
			return err
		}
		return out.Sync()
	}

	sh := getShellPath()
	cmd := exec.Command("nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "--", sh, "-c", "cat > "+shellQuote(dstHost))
	cmd.Stdin = in
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("%v: %s", err, stderr.String())
	}
	return nil
}

func chmodHost(path string, mode os.FileMode) error {
	if !isRunningInContainer() {
		return os.Chmod(path, mode.Perm())
	}
	out, err := runHostCommand(getShellPath(), fmt.Sprintf("chmod %o %s", mode.Perm(), shellQuote(path)))
	if err != nil {
		return fmt.Errorf("%v: %s", err, strings.TrimSpace(out))
	}
	return nil
}

func runSystemctl(action, service string) (string, error) {
	cmd := fmt.Sprintf("systemctl %s %s", action, service)
	out, err := runHostCommand(getShellPath(), cmd)
	return strings.TrimSpace(out), err
}

// writeContentToHost 把字符串内容写到宿主机文件。
func writeContentToHost(content, path string) error {
	if !isRunningInContainer() {
		return os.WriteFile(path, []byte(content), 0644)
	}
	out, err := runHostCommand(getShellPath(), fmt.Sprintf("cat > %s <<'AGENT_EOF'\n%s\nAGENT_EOF\n", shellQuote(path), content))
	_ = out
	return err
}

// mergeConfigOnHost 合并新 config 内容与宿主机现有 config，保护 6 个环境私有字段：
// server.url / server.token / agent.uuid / agent.name / agent.ip / deploy.deploy_dir
// 新内容覆盖其他所有字段。
func mergeConfigOnHost(newContent string) (string, error) {
	configPath := filepath.Join(config.GlobalConfig.Deploy.DeployDir, "config.yaml")

	// 读宿主机现有 config
	var oldContent string
	if !isRunningInContainer() {
		data, err := os.ReadFile(configPath)
		if err == nil {
			oldContent = string(data)
		}
	} else {
		out, err := runHostCommand(getShellPath(), fmt.Sprintf("cat %s 2>/dev/null || true", shellQuote(configPath)))
		if err == nil {
			oldContent = out
		}
	}

	if oldContent == "" {
		// 宿主机没有旧 config，直接返回新内容
		return newContent, nil
	}

	// 用通用 map 解析 YAML（避免循环 import config.Config 类型）
	var oldMap map[string]interface{}
	var newMap map[string]interface{}
	if err := yaml.Unmarshal([]byte(oldContent), &oldMap); err != nil {
		log.Printf("[UPDATE] mergeConfigOnHost: parse old config failed: %v, skip merge", err)
		return newContent, nil
	}
	if err := yaml.Unmarshal([]byte(newContent), &newMap); err != nil {
		return newContent, err
	}

	// 保护 6 个字段，从 old 拷回 new
	protectKeys := [][]string{
		{"server", "url"},
		{"server", "token"},
		{"agent", "uuid"},
		{"agent", "name"},
		{"agent", "ip"},
		{"deploy", "deploy_dir"},
	}
	for _, keys := range protectKeys {
		if len(keys) == 2 {
			oldSec, ok := oldMap[keys[0]].(map[string]interface{})
			if !ok {
				continue
			}
			if val, exists := oldSec[keys[1]]; exists {
				if _, ok := newMap[keys[0]].(map[string]interface{}); !ok {
					newMap[keys[0]] = map[string]interface{}{}
				}
				newMap[keys[0]].(map[string]interface{})[keys[1]] = val
			}
		}
	}

	out, err := yaml.Marshal(newMap)
	if err != nil {
		return newContent, err
	}
	return string(out), nil
}
