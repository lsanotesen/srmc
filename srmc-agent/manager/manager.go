package manager

import (
	"bufio"
	"bytes"
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

// resolveComposePath resolves the compose path to a valid compose file path.
// If the path is a directory, it looks for docker-compose.yml or compose.yaml in it.
func resolveComposePath(composePath string) (string, string, error) {
	if composePath == "" {
		return "", "", fmt.Errorf("no compose path configured")
	}

	// Check if it's a file directly
	if info, err := os.Stat(composePath); err == nil && !info.IsDir() {
		dir := filepath.Dir(composePath)
		return composePath, dir, nil
	}

	// Check if it's a directory - look for compose files
	if info, err := os.Stat(composePath); err == nil && info.IsDir() {
		candidates := []string{
			filepath.Join(composePath, "docker-compose.yml"),
			filepath.Join(composePath, "docker-compose.yaml"),
			filepath.Join(composePath, "compose.yaml"),
			filepath.Join(composePath, "compose.yml"),
		}
		for _, candidate := range candidates {
			if _, err := os.Stat(candidate); err == nil {
				return candidate, composePath, nil
			}
		}
		return "", "", fmt.Errorf("no compose file found in directory: %s", composePath)
	}

	return "", "", fmt.Errorf("compose path not found: %s", composePath)
}

// getDockerComposeCmd 返回可用的 docker compose 命令。
// 注意：此函数仅用于需要 context 的场景（如日志流）。
// 其他场景请使用 runComposeCmd 以获得更好的兼容性处理。
func getDockerComposeCmd() string {
	if _, err := exec.LookPath("docker"); err == nil {
		return "docker"
	}
	return "docker-compose"
}

// runComposeCmd 执行 docker compose 命令，自动在 docker compose (V2) 和 docker-compose (V1) 之间切换。
// 同时处理 Docker API 版本不匹配问题（如 client version 1.44 vs daemon 1.43）。
// 不指定 -p 项目名：让 compose 使用 yml 里的 name 字段（用户已为每个 yml 配置唯一 name）。
// 策略：先试 V2，V2 失败（任何原因）都尝试 V1，V1 也失败才返回错误。
func runComposeCmd(composeFile, workDir string, composeArgs ...string) ([]byte, error) {
	var v2Err, v1Err error
	var v2Output []byte

	// 尝试 docker compose (V2 插件模式)
	// 不指定 -p：让 compose 使用 yml 里的 name 字段（用户已配置唯一 name）
	if _, err := exec.LookPath("docker"); err == nil {
		fullArgs := append([]string{"docker", "compose", "-f", composeFile}, composeArgs...)
		v2Output, v2Err = execWithVersionFallback(fullArgs, workDir)
		if v2Err == nil {
			return v2Output, nil
		}
		log.Printf("[DEBUG] runComposeCmd V2 failed: %v, errStr=%s", v2Err, v2Output)
	}

	// 尝试 docker-compose (V1 独立命令)
	// 无论 V2 失败原因是什么，都尝试 V1
	if _, err := exec.LookPath("docker-compose"); err == nil {
		fullArgs := append([]string{"docker-compose", "-f", composeFile}, composeArgs...)
		output, err := execWithVersionFallback(fullArgs, workDir)
		if err == nil {
			if v2Err != nil {
				log.Printf("[DEBUG] runComposeCmd V1 succeeded after V2 failed")
			}
			return output, nil
		}
		v1Err = err
		log.Printf("[DEBUG] runComposeCmd V1 failed: %v, errStr=%s", v1Err, output)
	}

	if v2Err != nil && v1Err != nil {
		return v2Output, fmt.Errorf("docker compose (V2) failed: %v; docker-compose (V1) failed: %v", v2Err, v1Err)
	}
	if v2Err != nil {
		return v2Output, fmt.Errorf("docker compose (V2) failed: %v; docker-compose (V1) not installed", v2Err)
	}
	return nil, fmt.Errorf("docker-compose (V1) failed: %v; docker compose (V2) not installed", v1Err)
}

// runDockerCmd 执行 docker 命令，当遇到 API 版本不匹配错误时自动降级重试。
func runDockerCmd(args []string) ([]byte, error) {
	return execWithVersionFallback(args, "")
}

// execWithVersionFallback 执行 docker 命令，当遇到 API 版本不匹配错误时自动降级重试。
// 成功时只返回纯净的 stdout（避免 stderr 的 warning 污染输出）。
// 失败时返回 stderr+stdout 用于错误诊断。
func execWithVersionFallback(args []string, workDir string) ([]byte, error) {
	runOnce := func(env []string) ([]byte, []byte, error) {
		c := exec.Command(args[0], args[1:]...)
		c.Dir = workDir
		if len(env) > 0 {
			c.Env = env
		}
		var stdout, stderr bytes.Buffer
		c.Stdout = &stdout
		c.Stderr = &stderr
		err := c.Run()
		return stdout.Bytes(), stderr.Bytes(), err
	}

	stdout, stderr, err := runOnce(nil)
	if err == nil {
		return stdout, nil
	}

	errStr := string(stderr) + string(stdout)
	if strings.Contains(errStr, "is too new") || strings.Contains(errStr, "client version") {
		re := regexp.MustCompile(`Maximum supported API version is ([0-9.]+)`)
		match := re.FindStringSubmatch(errStr)
		fallbackVersion := "1.43"
		if len(match) >= 2 {
			fallbackVersion = match[1]
		}

		stdout2, stderr2, err2 := runOnce(append(os.Environ(), "DOCKER_API_VERSION="+fallbackVersion))
		if err2 == nil {
			// 写回全局环境变量，后续命令直接用协商版本，不再反复先失败再降级
			if os.Getenv("DOCKER_API_VERSION") != fallbackVersion {
				os.Setenv("DOCKER_API_VERSION", fallbackVersion)
				log.Printf("[INFO] Docker API version downgraded to %s successfully", fallbackVersion)
			}
			return stdout2, nil
		}
		return append(stderr2, stdout2...), err2
	}

	return append(stderr, stdout...), err
}

// getShellPath returns the path to the best available shell for executing commands.
// Prefers bash (supports bash syntax like $(), [[]], etc.) over sh.
func getShellPath() string {
	// Try bash first (supports bash syntax)
	if path, err := exec.LookPath("bash"); err == nil {
		return path
	}
	// Fallback to /bin/bash
	if _, err := os.Stat("/bin/bash"); err == nil {
		return "/bin/bash"
	}
	// Fallback to /usr/bin/bash
	if _, err := os.Stat("/usr/bin/bash"); err == nil {
		return "/usr/bin/bash"
	}
	// Fallback to sh
	if path, err := exec.LookPath("sh"); err == nil {
		return path
	}
	return "/bin/sh"
}

// isRunningInContainer detects if the agent is running inside a Docker container.
// When running in a container, we need nsenter to execute commands on the host
// (because the container doesn't have the host's users, home dirs, etc.)
func isRunningInContainer() bool {
	// Check for /.dockerenv (Docker creates this file)
	if _, err := os.Stat("/.dockerenv"); err == nil {
		return true
	}
	// Check if /proc/1/cgroup mentions docker
	if data, err := os.ReadFile("/proc/1/cgroup"); err == nil {
		content := string(data)
		if strings.Contains(content, "docker") || strings.Contains(content, "containerd") {
			return true
		}
	}
	return false
}

// runHostCommand executes a command, using nsenter when running in a container.
// This ensures commands like `su - isi` work because they run in the host's
// mount namespace (where /etc/passwd has the isi user, /u01 is writable, etc.)
func runHostCommand(shell string, finalCmd string) (string, error) {
	if isRunningInContainer() {
		// nsenter -t 1: target PID 1 (init process on host)
		// -m: mount namespace (host filesystem)
		// -u: UTS namespace (hostname)
		// -i: IPC namespace
		// -n: network namespace
		// -p: PID namespace
		log.Printf("[DEBUG] Running in container, using nsenter to execute on host")
		cmd := exec.Command("nsenter", "-t", "1", "-m", "-u", "-i", "-n", "-p", "--", shell, "-c", finalCmd)
		output, err := cmd.CombinedOutput()
		return string(output), err
	}
	// Not in container, execute directly
	cmd := exec.Command(shell, "-c", finalCmd)
	output, err := cmd.CombinedOutput()
	return string(output), err
}

type LogLine struct {
	ServiceID string `json:"service_id"`
	Line      string `json:"line"`
	Timestamp int64  `json:"timestamp"`
}

type LogStreamFunc func(LogLine)

type ServiceConfig struct {
	ServiceID    string `json:"service_id"`
	Name         string `json:"name"`
	Username     string `json:"username"` // SSH用户名
	DeployType   string `json:"deploy_type"`
	PIDFile      string `json:"pid_file"`
	Port         int    `json:"port"`
	StartCmd     string `json:"start_cmd"`
	StopCmd      string `json:"stop_cmd"`
	RestartCmd   string `json:"restart_cmd"`
	LogPath      string `json:"log_path"`
	DockerName   string `json:"docker_name"`
	ComposePath  string `json:"compose_path"`
	ImageName    string `json:"image_name"`
	PortMapping  string `json:"port_mapping"`
}

type CommandResult struct {
	Success bool   `json:"success"`
	Output  string `json:"output"`
	Error   string `json:"error"`
}

func Init() {
}

func StartService(svc ServiceConfig) CommandResult {
	switch svc.DeployType {
	case "PROCESS":
		return startProcess(svc)
	case "DOCKER":
		return startDocker(svc)
	case "DOCKER_COMPOSE":
		return startCompose(svc)
	default:
		return CommandResult{Success: false, Error: "Unknown deploy type"}
	}
}

func StopService(svc ServiceConfig) CommandResult {
	switch svc.DeployType {
	case "PROCESS":
		return stopProcess(svc)
	case "DOCKER":
		return stopDocker(svc)
	case "DOCKER_COMPOSE":
		return stopCompose(svc)
	default:
		return CommandResult{Success: false, Error: "Unknown deploy type"}
	}
}

func RestartService(svc ServiceConfig) CommandResult {
	switch svc.DeployType {
	case "PROCESS":
		return restartProcess(svc)
	case "DOCKER":
		return restartDocker(svc)
	case "DOCKER_COMPOSE":
		return restartCompose(svc)
	default:
		return CommandResult{Success: false, Error: "Unknown deploy type"}
	}
}

func startProcess(svc ServiceConfig) CommandResult {
	if svc.StartCmd == "" {
		return CommandResult{Success: false, Error: "No start command configured"}
	}

	// 展开路径并确定工作目录
	expandedCmd, workDir, scriptName := expandCmdAndWorkDir(svc.StartCmd, svc.Username)

	log.Printf("[DEBUG] startProcess: original_cmd=%s", svc.StartCmd)
	log.Printf("[DEBUG] startProcess: expanded_cmd=%s", expandedCmd)
	log.Printf("[DEBUG] startProcess: workDir=%s", workDir)
	log.Printf("[DEBUG] startProcess: scriptName=%s", scriptName)
	log.Printf("[DEBUG] startProcess: username=%s", svc.Username)

	// 获取可用的 shell
	shell := getShellPath()
	log.Printf("[DEBUG] startProcess: using shell=%s", shell)

	// 构建执行命令：先 cd 到脚本目录，再执行脚本
	var innerCmd string
	if workDir != "" && scriptName != "" {
		// 确保脚本有执行权限
		scriptFullPath := filepath.Join(workDir, scriptName)
		os.Chmod(scriptFullPath, 0755)
		// cd 到工作目录，然后用 ./scriptName 执行
		innerCmd = fmt.Sprintf("cd %s && ./%s", workDir, scriptName)
	} else {
		// 回退：直接执行展开后的命令
		innerCmd = expandedCmd
	}

	// 关键：如果指定了 username 且当前是 root，用 su - <user> 切换用户执行
	// 这样脚本会以正确的用户身份运行，环境变量、权限、home 目录都正确
	var finalCmd string
	if svc.Username != "" && os.Getuid() == 0 {
		finalCmd = fmt.Sprintf("su - %s -c '%s'", svc.Username, innerCmd)
	} else {
		finalCmd = innerCmd
	}

	log.Printf("[DEBUG] startProcess: finalCmd=%s", finalCmd)

	// 执行命令（容器内自动用 nsenter 进入宿主机命名空间）
	output, err := runHostCommand(shell, finalCmd)
	log.Printf("[DEBUG] startProcess: err=%v", err)
	log.Printf("[DEBUG] startProcess: output=%s", output)

	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: output}
	}

	return CommandResult{Success: true, Output: output}
}

// expandCmdAndWorkDir 展开命令中的路径，并确定工作目录
// 返回值: expandedCmd(展开后的完整命令), workDir(工作目录), scriptName(脚本文件名)
func expandCmdAndWorkDir(cmd string, username string) (string, string, string) {
	// 查找命令中的文件路径（如 start.sh, /path/to/script.sh）
	// 提取第一个文件路径作为工作目录
	parts := strings.Fields(cmd)
	var scriptPath string
	var workDir string

	for i, part := range parts {
		if strings.HasSuffix(part, ".sh") || strings.HasSuffix(part, ".py") || strings.HasSuffix(part, ".jar") || strings.HasSuffix(part, ".exe") {
			scriptPath = part
			_ = i
			break
		}
	}

	// 如果没找到脚本，尝试找包含路径的参数
	if scriptPath == "" {
		for _, part := range parts {
			if strings.Contains(part, "/") {
				scriptPath = part
				break
			}
		}
	}

	// 展开 ~ 路径
	if strings.HasPrefix(cmd, "~") {
		homeDir := getHomeDir(username)
		cmd = homeDir + cmd[1:]
		if scriptPath != "" && strings.HasPrefix(scriptPath, "~") {
			scriptPath = homeDir + scriptPath[1:]
		}
	} else if scriptPath != "" && strings.HasPrefix(scriptPath, "~") {
		homeDir := getHomeDir(username)
		scriptPath = homeDir + scriptPath[1:]
		// 替换命令中的 ~
		cmd = strings.Replace(cmd, "~", homeDir, 1)
	}

	// 如果找到了脚本路径，设置工作目录为脚本所在目录
	scriptName := ""
	if scriptPath != "" {
		absPath, err := filepath.Abs(scriptPath)
		if err == nil {
			// 如果是脚本文件，workDir 为脚本所在目录
			if !strings.HasSuffix(absPath, ".jar") {
				info, statErr := os.Stat(absPath)
				if statErr == nil && !info.IsDir() {
					workDir = filepath.Dir(absPath)
					scriptName = filepath.Base(absPath)
				} else if statErr == nil && info.IsDir() {
					workDir = absPath
				}
			} else {
				// jar 文件
				workDir = filepath.Dir(absPath)
				scriptName = filepath.Base(absPath)
			}
		}
	}

	return cmd, workDir, scriptName
}

// getHomeDir 获取用户的 home 目录
func getHomeDir(username string) string {
	if username != "" {
		// 从 /etc/passwd 查找
		if data, err := os.ReadFile("/etc/passwd"); err == nil {
			for _, line := range strings.Split(string(data), "\n") {
				line = strings.TrimSpace(line)
				if line == "" || strings.HasPrefix(line, "#") {
					continue
				}
				fields := strings.Split(line, ":")
				if len(fields) >= 6 && fields[0] == username {
					return fields[5]
				}
			}
		}

		// 常见的 home 目录模式
		commonPaths := []string{
			"/home/" + username,
			"/u01/" + username,
			"/u02/" + username,
		}

		for _, p := range commonPaths {
			if info, err := os.Stat(p); err == nil && info.IsDir() {
				return p
			}
		}
	}

	// 返回当前用户的 home
	if home, err := os.UserHomeDir(); err == nil {
		return home
	}

	return "/root"
}

func stopProcess(svc ServiceConfig) CommandResult {
	if svc.StopCmd == "" {
		return CommandResult{Success: false, Error: "No stop command configured"}
	}

	// 展开路径并确定工作目录
	expandedCmd, workDir, scriptName := expandCmdAndWorkDir(svc.StopCmd, svc.Username)

	log.Printf("[DEBUG] stopProcess: original_cmd=%s", svc.StopCmd)
	log.Printf("[DEBUG] stopProcess: expanded_cmd=%s", expandedCmd)
	log.Printf("[DEBUG] stopProcess: workDir=%s", workDir)
	log.Printf("[DEBUG] stopProcess: scriptName=%s", scriptName)
	log.Printf("[DEBUG] stopProcess: username=%s", svc.Username)

	// 构建执行命令
	var innerCmd string
	if workDir != "" && scriptName != "" {
		scriptFullPath := filepath.Join(workDir, scriptName)
		os.Chmod(scriptFullPath, 0755)
		innerCmd = fmt.Sprintf("cd %s && ./%s", workDir, scriptName)
	} else {
		innerCmd = expandedCmd
	}

	// 如果指定了 username 且当前是 root，用 su 切换用户
	var finalCmd string
	if svc.Username != "" && os.Getuid() == 0 {
		finalCmd = fmt.Sprintf("su - %s -c '%s'", svc.Username, innerCmd)
	} else {
		finalCmd = innerCmd
	}

	log.Printf("[DEBUG] stopProcess: finalCmd=%s", finalCmd)

	output, err := runHostCommand(getShellPath(), finalCmd)
	log.Printf("[DEBUG] stopProcess: err=%v", err)
	log.Printf("[DEBUG] stopProcess: output=%s", output)

	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: output}
	}

	return CommandResult{Success: true, Output: output}
}

func restartProcess(svc ServiceConfig) CommandResult {
	if svc.RestartCmd != "" {
		expandedCmd, workDir, scriptName := expandCmdAndWorkDir(svc.RestartCmd, svc.Username)
		var innerCmd string
		if workDir != "" && scriptName != "" {
			scriptFullPath := filepath.Join(workDir, scriptName)
			os.Chmod(scriptFullPath, 0755)
			innerCmd = fmt.Sprintf("cd %s && ./%s", workDir, scriptName)
		} else {
			innerCmd = expandedCmd
		}
		var finalCmd string
		if svc.Username != "" && os.Getuid() == 0 {
			finalCmd = fmt.Sprintf("su - %s -c '%s'", svc.Username, innerCmd)
		} else {
			finalCmd = innerCmd
		}
		log.Printf("[DEBUG] restartProcess: finalCmd=%s", finalCmd)
		output, err := runHostCommand(getShellPath(), finalCmd)

		if err != nil {
			return CommandResult{Success: false, Error: err.Error(), Output: output}
		}

		return CommandResult{Success: true, Output: output}
	}

	stopResult := stopProcess(svc)
	if !stopResult.Success {
		return stopResult
	}

	time.Sleep(2 * time.Second)

	return startProcess(svc)
}

func startDocker(svc ServiceConfig) CommandResult {
	if svc.DockerName == "" {
		return CommandResult{Success: false, Error: "No container name configured"}
	}

	output, err := runDockerCmd([]string{"docker", "start", svc.DockerName})
	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
}

func stopDocker(svc ServiceConfig) CommandResult {
	if svc.DockerName == "" {
		return CommandResult{Success: false, Error: "No container name configured"}
	}

	output, err := runDockerCmd([]string{"docker", "stop", "-t", "10", svc.DockerName})
	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
}

func restartDocker(svc ServiceConfig) CommandResult {
	if svc.DockerName == "" {
		return CommandResult{Success: false, Error: "No container name configured"}
	}

	output, err := runDockerCmd([]string{"docker", "restart", "-t", "10", svc.DockerName})
	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
}

func startCompose(svc ServiceConfig) CommandResult {
	log.Printf("[DEBUG] startCompose: ComposePath=%s, DockerName=%s", svc.ComposePath, svc.DockerName)
	
	composeFile, workDir, err := resolveComposePath(svc.ComposePath)
	if err != nil {
		log.Printf("[ERROR] startCompose: resolveComposePath failed: %v (path=%s)", err, svc.ComposePath)
		return CommandResult{Success: false, Error: fmt.Sprintf("找不到 docker-compose 文件: %v (路径: %s)", err, svc.ComposePath)}
	}

	log.Printf("[DEBUG] startCompose: resolved composeFile=%s, workDir=%s", composeFile, workDir)

	// 检查 compose 文件是否可读
	if _, statErr := os.Stat(composeFile); statErr != nil {
		log.Printf("[ERROR] startCompose: compose file not accessible: %v", statErr)
		return CommandResult{Success: false, Error: fmt.Sprintf("compose 文件不可访问: %v", statErr)}
	}

	log.Printf("[INFO] startCompose: executing compose up -d")

	output, err := runComposeCmd(composeFile, workDir, "up", "-d")
	outputStr := string(output)
	
	if err != nil {
		log.Printf("[ERROR] startCompose: command failed: %v, output: %s", err, outputStr)
		return CommandResult{Success: false, Error: fmt.Sprintf("docker compose 执行失败: %v", err), Output: outputStr}
	}

	log.Printf("[INFO] startCompose: command succeeded, output: %s", outputStr)
	return CommandResult{Success: true, Output: outputStr}
}

func stopCompose(svc ServiceConfig) CommandResult {
	composeFile, workDir, err := resolveComposePath(svc.ComposePath)
	if err != nil {
		return CommandResult{Success: false, Error: err.Error()}
	}

	output, err := runComposeCmd(composeFile, workDir, "down")
	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
}

func restartCompose(svc ServiceConfig) CommandResult {
	composeFile, workDir, err := resolveComposePath(svc.ComposePath)
	if err != nil {
		return CommandResult{Success: false, Error: err.Error()}
	}

	output, err := runComposeCmd(composeFile, workDir, "restart")
	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
}

func StreamLogs(svc ServiceConfig, callback LogStreamFunc) error {
	switch svc.DeployType {
	case "PROCESS":
		return streamProcessLogs(svc, callback)
	case "DOCKER":
		return streamDockerLogs(svc, callback)
	case "DOCKER_COMPOSE":
		return streamComposeLogs(svc, callback)
	default:
		return fmt.Errorf("Unknown deploy type")
	}
}

func streamProcessLogs(svc ServiceConfig, callback LogStreamFunc) error {
	if svc.LogPath == "" {
		return fmt.Errorf("No log path configured")
	}

	// 展开日志路径
	logPath := expandLogPath(svc.LogPath, svc.Username)
	log.Printf("[DEBUG] streamProcessLogs: original_log_path=%s, expanded_log_path=%s", svc.LogPath, logPath)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	cmd := exec.CommandContext(ctx, "tail", "-F", logPath)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}

	if err := cmd.Start(); err != nil {
		return err
	}

	scanner := bufio.NewScanner(stdout)
	for scanner.Scan() {
		callback(LogLine{
			ServiceID: svc.ServiceID,
			Line:      scanner.Text(),
			Timestamp: time.Now().Unix(),
		})
	}

	return cmd.Wait()
}

// expandLogPath 展开日志路径中的 ~
func expandLogPath(logPath string, username string) string {
	if strings.HasPrefix(logPath, "~") {
		homeDir := getHomeDir(username)
		return homeDir + logPath[1:]
	}
	return logPath
}

func streamDockerLogs(svc ServiceConfig, callback LogStreamFunc) error {
	if svc.DockerName == "" {
		return fmt.Errorf("No container name configured")
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	cmd := exec.CommandContext(ctx, "docker", "logs", "-f", svc.DockerName)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}

	stderr, err := cmd.StderrPipe()
	if err != nil {
		return err
	}

	if err := cmd.Start(); err != nil {
		return err
	}

	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			callback(LogLine{
				ServiceID: svc.ServiceID,
				Line:      scanner.Text(),
				Timestamp: time.Now().Unix(),
			})
		}
	}()

	go func() {
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			callback(LogLine{
				ServiceID: svc.ServiceID,
				Line:      scanner.Text(),
				Timestamp: time.Now().Unix(),
			})
		}
	}()

	return cmd.Wait()
}

func streamComposeLogs(svc ServiceConfig, callback LogStreamFunc) error {
	composeFile, workDir, err := resolveComposePath(svc.ComposePath)
	if err != nil {
		return err
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	dockerCmd := getDockerComposeCmd()
	var cmd *exec.Cmd
	if dockerCmd == "docker" {
		cmd = exec.CommandContext(ctx, "docker", "compose", "-f", composeFile, "logs", "-f")
	} else {
		cmd = exec.CommandContext(ctx, "docker-compose", "-f", composeFile, "logs", "-f")
	}
	cmd.Dir = workDir

	log.Printf("[DEBUG] streamComposeLogs: cmd=%v, workDir=%s", cmd.Args, workDir)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}

	stderr, err := cmd.StderrPipe()
	if err != nil {
		return err
	}

	if err := cmd.Start(); err != nil {
		return err
	}

	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			callback(LogLine{
				ServiceID: svc.ServiceID,
				Line:      scanner.Text(),
				Timestamp: time.Now().Unix(),
			})
		}
	}()

	go func() {
		scanner := bufio.NewScanner(stderr)
		for scanner.Scan() {
			callback(LogLine{
				ServiceID: svc.ServiceID,
				Line:      scanner.Text(),
				Timestamp: time.Now().Unix(),
			})
		}
	}()

	return cmd.Wait()
}