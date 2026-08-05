package manager

import (
	"bufio"
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
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

// getDockerComposeCmd returns the docker compose command to use.
// Prefers "docker compose" (newer) over "docker-compose" (older).
func getDockerComposeCmd() string {
	// Try "docker compose" first (Docker v2)
	if _, err := exec.LookPath("docker"); err == nil {
		return "docker"
	}
	// Fallback to "docker-compose"
	return "docker-compose"
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

	// 使用 bash 执行（支持 bash 语法）
	command := exec.Command("/bin/bash", "-c", finalCmd)

	output, err := command.CombinedOutput()
	log.Printf("[DEBUG] startProcess: err=%v", err)
	log.Printf("[DEBUG] startProcess: output=%s", string(output))

	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
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

	command := exec.Command("/bin/bash", "-c", finalCmd)

	output, err := command.CombinedOutput()
	log.Printf("[DEBUG] stopProcess: err=%v", err)
	log.Printf("[DEBUG] stopProcess: output=%s", string(output))

	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
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
		command := exec.Command("/bin/bash", "-c", finalCmd)
		output, err := command.CombinedOutput()

		if err != nil {
			return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
		}

		return CommandResult{Success: true, Output: string(output)}
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

	cmd := exec.Command("docker", "start", svc.DockerName)
	output, err := cmd.CombinedOutput()

	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
}

func stopDocker(svc ServiceConfig) CommandResult {
	if svc.DockerName == "" {
		return CommandResult{Success: false, Error: "No container name configured"}
	}

	cmd := exec.Command("docker", "stop", "-t", "10", svc.DockerName)
	output, err := cmd.CombinedOutput()

	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
}

func restartDocker(svc ServiceConfig) CommandResult {
	if svc.DockerName == "" {
		return CommandResult{Success: false, Error: "No container name configured"}
	}

	cmd := exec.Command("docker", "restart", "-t", "10", svc.DockerName)
	output, err := cmd.CombinedOutput()

	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
}

func startCompose(svc ServiceConfig) CommandResult {
	composeFile, workDir, err := resolveComposePath(svc.ComposePath)
	if err != nil {
		return CommandResult{Success: false, Error: err.Error()}
	}

	dockerCmd := getDockerComposeCmd()
	var cmd *exec.Cmd
	if dockerCmd == "docker" {
		cmd = exec.Command("docker", "compose", "-f", composeFile, "up", "-d")
	} else {
		cmd = exec.Command("docker-compose", "-f", composeFile, "up", "-d")
	}
	cmd.Dir = workDir

	log.Printf("[DEBUG] startCompose: cmd=%v, workDir=%s", cmd.Args, workDir)

	output, err := cmd.CombinedOutput()
	if err != nil {
		return CommandResult{Success: false, Error: err.Error(), Output: string(output)}
	}

	return CommandResult{Success: true, Output: string(output)}
}

func stopCompose(svc ServiceConfig) CommandResult {
	composeFile, workDir, err := resolveComposePath(svc.ComposePath)
	if err != nil {
		return CommandResult{Success: false, Error: err.Error()}
	}

	dockerCmd := getDockerComposeCmd()
	var cmd *exec.Cmd
	if dockerCmd == "docker" {
		cmd = exec.Command("docker", "compose", "-f", composeFile, "down")
	} else {
		cmd = exec.Command("docker-compose", "-f", composeFile, "down")
	}
	cmd.Dir = workDir

	log.Printf("[DEBUG] stopCompose: cmd=%v, workDir=%s", cmd.Args, workDir)

	output, err := cmd.CombinedOutput()
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

	dockerCmd := getDockerComposeCmd()
	var cmd *exec.Cmd
	if dockerCmd == "docker" {
		cmd = exec.Command("docker", "compose", "-f", composeFile, "restart")
	} else {
		cmd = exec.Command("docker-compose", "-f", composeFile, "restart")
	}
	cmd.Dir = workDir

	log.Printf("[DEBUG] restartCompose: cmd=%v, workDir=%s", cmd.Args, workDir)

	output, err := cmd.CombinedOutput()
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