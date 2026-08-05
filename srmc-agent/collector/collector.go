package collector

import (
	"fmt"
	"log"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/load"
	"github.com/shirou/gopsutil/v3/mem"

	"srmc-agent/config"
)

type ServiceConfig struct {
	ServiceID   string `json:"service_id"`
	Name        string `json:"name"`
	Username    string `json:"username"` // SSH用户名，用于解析 ~ 路径
	DeployType  string `json:"deploy_type"`
	PIDFile     string `json:"pid_file"`
	Port        int    `json:"port"`
	Ports       string `json:"ports"`
	HealthURL   string `json:"health_url"`
	StartCmd    string `json:"start_cmd"`
	StopCmd     string `json:"stop_cmd"`
	RestartCmd  string `json:"restart_cmd"`
	LogPath     string `json:"log_path"`
	DockerName  string `json:"docker_name"`
	ComposePath string `json:"compose_path"`
	ProgramPath string `json:"program_path"`
}

type ServiceStatus struct {
	ServiceID    string            `json:"service_id"`
	Name         string            `json:"name"`
	Status       string            `json:"status"`
	PID          int               `json:"pid"`
	Port         int               `json:"port"`
	DeployType   string            `json:"deploy_type"`
	RunningSince int64             `json:"running_since"`
	Containers   []ContainerDetail `json:"containers,omitempty"`
}

// ContainerDetail 描述 Docker Compose 服务下单个容器的状态
type ContainerDetail struct {
	ID      string `json:"id"`       // 容器 ID（短）
	Name    string `json:"name"`     // 容器名称
	State   string `json:"state"`    // 容器状态（running/exited/dead/paused/restarting）
	Status  string `json:"status"`   // 人类可读状态（如 Up 2 hours、Exited (0) 5 minutes ago）
	Image   string `json:"image"`    // 镜像名称
	Ports   string `json:"ports"`    // 端口映射
	Running bool   `json:"running"`  // 是否运行中
}

type SystemMetrics struct {
	CPUPercent    float64 `json:"cpu_percent"`
	MemoryPercent float64 `json:"memory_percent"`
	SwapPercent   float64 `json:"swap_percent"`
	DiskPercent   float64 `json:"disk_percent"`
	Load1         float64 `json:"load1"`
	Load5         float64 `json:"load5"`
	Load15        float64 `json:"load15"`
	Uptime        uint64  `json:"uptime"`
	Hostname      string  `json:"hostname"`
	IP            string  `json:"ip"`
	OS            string  `json:"os"`
	Kernel        string  `json:"kernel"`
	CPUModel      string  `json:"cpu_model"`
	CPUCores      int     `json:"cpu_cores"`
	MemoryTotal   uint64  `json:"memory_total"`
}

var services []ServiceConfig
var lastMetrics SystemMetrics

func Init() {
}

func UpdateServices(newServices []ServiceConfig) {
	services = newServices
	log.Printf("Updated services: %d", len(services))
}

func CollectSystemMetrics() SystemMetrics {
	cpuPercent, _ := cpu.Percent(time.Second, false)
	memInfo, _ := mem.VirtualMemory()
	swapInfo, _ := mem.SwapMemory()
	diskInfo, _ := disk.Usage("/")
	loadInfo, _ := load.Avg()
	hostInfo, _ := host.Info()
	cpuInfo, _ := cpu.Info()

	hostname := hostInfo.Hostname
	if config.GlobalConfig.Agent.Name != "" {
		hostname = config.GlobalConfig.Agent.Name
	}

	ip := getLocalIP()
	if config.GlobalConfig.Agent.IP != "" {
		ip = config.GlobalConfig.Agent.IP
	} else {
		hostIP := getHostIP()
		if hostIP != "" {
			ip = hostIP
		}
	}

	metrics := SystemMetrics{
		CPUPercent:    cpuPercent[0],
		MemoryPercent: memInfo.UsedPercent,
		SwapPercent:   swapInfo.UsedPercent,
		DiskPercent:   diskInfo.UsedPercent,
		Load1:         loadInfo.Load1,
		Load5:         loadInfo.Load5,
		Load15:        loadInfo.Load15,
		Uptime:        hostInfo.Uptime,
		Hostname:      hostname,
		IP:            ip,
		OS:            hostInfo.OS,
		Kernel:        hostInfo.KernelVersion,
		MemoryTotal:   memInfo.Total,
	}

	if len(cpuInfo) > 0 {
		metrics.CPUModel = cpuInfo[0].ModelName
		metrics.CPUCores = len(cpuInfo)
	}

	lastMetrics = metrics
	return metrics
}

func getHostIP() string {
	if ip := getHostIPFromEnv(); ip != "" {
		return ip
	}

	if ip := getHostIPFromHostsFile(); ip != "" {
		return ip
	}

	if ip := getHostIPFromDNS(); ip != "" {
		return ip
	}

	if ip := getHostIPFromDockerGateway(); ip != "" {
		return ip
	}

	if ip := getHostIPFromRoute(); ip != "" {
		return ip
	}

	return ""
}

func getHostIPFromHostsFile() string {
	cmd := exec.Command("cat", "/etc/hosts")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return ""
	}

	lines := strings.Split(string(output), "\n")
	for _, line := range lines {
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			if parts[1] == "host.docker.internal" || parts[1] == "gateway" {
				log.Printf("Using host IP from /etc/hosts: %s", parts[0])
				return parts[0]
			}
		}
	}
	return ""
}

func getHostIPFromDNS() string {
	cmd := exec.Command("getent", "hosts", "host.docker.internal")
	output, err := cmd.CombinedOutput()
	if err == nil && len(output) > 0 {
		parts := strings.Fields(string(output))
		if len(parts) > 0 {
			return parts[0]
		}
	}
	return ""
}

func getHostIPFromDockerGateway() string {
	cmd := exec.Command("docker", "network", "inspect", "-f", "{{range .IPAM.Config}}{{.Gateway}}{{end}}", "srmc_default")
	output, err := cmd.CombinedOutput()
	if err == nil && len(output) > 0 {
		gateway := strings.TrimSpace(string(output))
		if gateway != "" && gateway != "<no value>" {
			return gateway
		}
	}
	return ""
}

func getHostIPFromEnv() string {
	if ip := os.Getenv("HOST_IP"); ip != "" {
		log.Printf("Using HOST_IP from environment: %s", ip)
		return ip
	}
	return ""
}

func getHostIPFromRoute() string {
	cmd := exec.Command("ip", "route", "show", "default")
	output, err := cmd.CombinedOutput()
	if err != nil {
		return ""
	}

	parts := strings.Fields(string(output))
	for i, part := range parts {
		if part == "via" && i+1 < len(parts) {
			return parts[i+1]
		}
	}
	return ""
}

func CollectServiceStatus() []ServiceStatus {
	statuses := make([]ServiceStatus, 0, len(services))

	for _, svc := range services {
		status := collectSingleService(svc)
		statuses = append(statuses, status)
	}

	return statuses
}

func collectSingleService(svc ServiceConfig) ServiceStatus {
	status := ServiceStatus{
		ServiceID:  svc.ServiceID,
		Name:       svc.Name,
		DeployType: svc.DeployType,
		Port:       svc.Port,
	}

	switch svc.DeployType {
	case "HOST", "PROCESS":
		status = collectProcessStatus(svc)
	case "DOCKER":
		status = collectDockerStatus(svc)
	case "DOCKER_COMPOSE":
		status = collectComposeStatus(svc)
	default:
		status.Status = "Unknown"
	}

	return status
}

func collectProcessStatus(svc ServiceConfig) ServiceStatus {
	status := ServiceStatus{
		ServiceID:  svc.ServiceID,
		Name:       svc.Name,
		DeployType: svc.DeployType,
		Port:       svc.Port,
		Status:     "Stopped",
	}

	log.Printf("[DEBUG] Collecting service %s (%s) status - PIDFile=%s, Port=%d, Ports=%s, ProgramPath=%s, StartCmd=%s",
		svc.ServiceID, svc.Name, svc.PIDFile, svc.Port, svc.Ports, svc.ProgramPath, svc.StartCmd)

	// 1. PID 文件检查
	if svc.PIDFile != "" {
		pid := readPIDFile(svc.PIDFile)
		log.Printf("[DEBUG] PID check: file=%s, pid=%d, running=%v", svc.PIDFile, pid, pid > 0 && isProcessRunningPure(pid))
		if pid > 0 && isProcessRunningPure(pid) {
			createTime, _ := getProcessCreateTime(pid)
			status.Status = "Running"
			status.PID = pid
			status.RunningSince = createTime / 1000
			log.Printf("[DEBUG] Found running via PID file: PID=%d", pid)
			return status
		}
	}

	// 2. 端口检查
	if svc.Port > 0 {
		listening := isPortListening(svc.Port)
		log.Printf("[DEBUG] Port check: port=%d, listening=%v", svc.Port, listening)
		if listening {
			status.Status = "Running"
			log.Printf("[DEBUG] Found running via port %d", svc.Port)
			return status
		}
	}

	if svc.Ports != "" {
		for _, portStr := range strings.Split(svc.Ports, ",") {
			portStr = strings.TrimSpace(portStr)
			if port, err := strconv.Atoi(portStr); err == nil && port > 0 {
				listening := isPortListening(port)
				log.Printf("[DEBUG] Multi-port check: port=%d, listening=%v", port, listening)
				if listening {
					status.Status = "Running"
					status.Port = port
					log.Printf("[DEBUG] Found running via port %d", port)
					return status
				}
			}
		}
	}

	// 3. 启动脚本解析（优先使用具体文件名，如 event-topic-extraction-new-server.jar）
	if svc.StartCmd != "" {
		executables := extractExecutablesFromCmd(svc.StartCmd)
		log.Printf("[DEBUG] StartCmd check: cmd=%s, executables=%v, username=%s", svc.StartCmd, executables, svc.Username)
		if pid := findProcessByStartCmd(svc.StartCmd, svc.Username); pid > 0 {
			status.Status = "Running"
			status.PID = pid
			if createTime, err := getProcessCreateTime(pid); err == nil {
				status.RunningSince = createTime / 1000
			}
			log.Printf("[DEBUG] Found running via start cmd: PID=%d", pid)
			return status
		}
	}

	// 4. ProgramPath 检查 - 已移除（basename 如 "server" 太通用，容易误匹配）

	// 5. 服务名兜底 - 仅当名称为英文且足够具体时才使用（避免中文名称误匹配）
	if svc.Name != "" && len(svc.Name) > 6 && isASCII(svc.Name) {
		log.Printf("[DEBUG] Name check: name=%s", svc.Name)
		if pid := findProcessByName(svc.Name); pid > 0 {
			status.Status = "Running"
			status.PID = pid
			log.Printf("[DEBUG] Found running via name: PID=%d", pid)
			return status
		}
	}

	log.Printf("[DEBUG] Service %s is STOPPED", svc.ServiceID)
	return status
}

func collectDockerStatus(svc ServiceConfig) ServiceStatus {
	status := ServiceStatus{
		ServiceID:  svc.ServiceID,
		Name:       svc.Name,
		DeployType: svc.DeployType,
		Port:       svc.Port,
		Status:     "Unknown",
	}

	if svc.DockerName == "" {
		return status
	}

	// 复用 inspectContainer 一次性获取状态、重启策略等信息
	container, err := inspectContainer(svc.DockerName)
	if err != nil {
		status.Status = "Stopped"
		return status
	}

	status.Containers = []ContainerDetail{container}

	if container.Running {
		status.Status = "Running"
	} else {
		status.Status = getContainerStatus(container.State)
	}

	// 采集容器创建时间作为 RunningSince
	cmd2 := exec.Command("docker", "inspect", "-f", "{{.Created}}", svc.DockerName)
	output2, _ := cmd2.CombinedOutput()
	if len(output2) > 0 {
		createdStr := strings.TrimSpace(string(output2))
		if t, err := time.Parse(time.RFC3339, createdStr); err == nil {
			status.RunningSince = t.Unix()
		}
	}

	return status
}

func collectComposeStatus(svc ServiceConfig) ServiceStatus {
	status := ServiceStatus{
		ServiceID:  svc.ServiceID,
		Name:       svc.Name,
		DeployType: svc.DeployType,
		Port:       svc.Port,
		Status:     "Unknown",
	}

	if svc.ComposePath == "" {
		log.Printf("[DEBUG] collectComposeStatus: no compose path configured for service %s", svc.ServiceID)
		return status
	}

	// 解析 compose 路径（支持目录和文件）
	composeFile, workDir, err := resolveComposePathForCollector(svc.ComposePath)
	if err != nil {
		log.Printf("[DEBUG] collectComposeStatus: resolve error: %v", err)
		status.Status = "Stopped"
		return status
	}

	log.Printf("[DEBUG] collectComposeStatus: composeFile=%s, workDir=%s, dockerName=%s", composeFile, workDir, svc.DockerName)

	// 构建 docker compose 命令
	dockerCmd := getDockerComposeCmd()
	var baseArgs []string
	if dockerCmd == "docker" {
		baseArgs = []string{"docker", "compose", "-f", composeFile}
	} else {
		baseArgs = []string{"docker-compose", "-f", composeFile}
	}

	// 如果指定了容器名称，只检查该容器
	if svc.DockerName != "" {
		container, err := inspectContainer(svc.DockerName)
		if err != nil {
			log.Printf("[DEBUG] collectComposeStatus: inspect %s error: %v", svc.DockerName, err)
			status.Status = "Stopped"
			status.Containers = []ContainerDetail{{
				ID:      svc.DockerName,
				Name:    svc.DockerName,
				State:   "unknown",
				Status:  "inspect failed: " + err.Error(),
				Running: false,
			}}
			return status
		}
		status.Containers = []ContainerDetail{container}
		if container.Running {
			status.Status = "Running"
		} else {
			status.Status = "Stopped"
		}
		log.Printf("[DEBUG] collectComposeStatus: container %s state=%s, status=%s",
			container.Name, container.State, container.Status)
		return status
	}

	// 获取所有容器 ID
	args := append(baseArgs, "ps", "-aq") // -a 包含已停止的容器
	cmd := exec.Command(args[0], args[1:]...)
	cmd.Dir = workDir
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Printf("[DEBUG] collectComposeStatus: ps error: %v, output: %s", err, string(output))
		status.Status = "Stopped"
		return status
	}

	containerIDs := strings.Split(strings.TrimSpace(string(output)), "\n")
	if len(containerIDs) == 1 && containerIDs[0] == "" {
		log.Printf("[DEBUG] collectComposeStatus: no containers found")
		status.Status = "Stopped"
		return status
	}

	log.Printf("[DEBUG] collectComposeStatus: found %d containers", len(containerIDs))

	// 检查每个容器状态
	containers := make([]ContainerDetail, 0, len(containerIDs))
	runningCount := 0
	for _, cid := range containerIDs {
		cid = strings.TrimSpace(cid)
		if cid == "" {
			continue
		}
		container, err := inspectContainer(cid)
		if err != nil {
			log.Printf("[DEBUG] collectComposeStatus: inspect %s error: %v", cid, err)
			containers = append(containers, ContainerDetail{
				ID:      truncateID(cid),
				Name:    cid,
				State:   "unknown",
				Status:  "inspect failed",
				Running: false,
			})
			continue
		}
		containers = append(containers, container)
		if container.Running {
			runningCount++
		}
	}

	status.Containers = containers
	totalCount := len(containers)

	log.Printf("[DEBUG] collectComposeStatus: running=%d/%d", runningCount, totalCount)

	if totalCount == 0 {
		status.Status = "Stopped"
	} else if runningCount == totalCount {
		status.Status = "Running"
	} else if runningCount > 0 {
		status.Status = "Partial"
	} else {
		status.Status = "Stopped"
	}

	return status
}

// inspectContainer 通过 docker inspect 获取容器详细信息
func inspectContainer(containerIDOrName string) (ContainerDetail, error) {
	// 使用 Go template 一次性获取所有需要的字段，避免多次调用 docker inspect
	// 端口映射格式: 遍历 NetworkSettings.Ports (map[port][]PortBinding)
	// 容器端口是 map 的 key（如 "3306/tcp"），HostPort 是 PortBinding 的字段
	format := `{{.Id}}|{{.Name}}|{{.State.Status}}|{{.State.Running}}|{{.Config.Image}}|{{range $port, $bindings := .NetworkSettings.Ports}}{{range $bindings}}{{$port}}->{{.HostPort}},{{end}}{{end}}|{{.State.Status}}`
	cmd := exec.Command("docker", "inspect", "-f", format, containerIDOrName)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return ContainerDetail{}, err
	}

	parts := strings.Split(strings.TrimSpace(string(out)), "|")
	if len(parts) < 6 {
		return ContainerDetail{}, fmt.Errorf("unexpected inspect output: %s", string(out))
	}

	fullID := parts[0]
	name := strings.TrimPrefix(parts[1], "/") // 容器名前缀有 /
	state := parts[2]
	image := parts[4]
	ports := parts[5]

	// 人类可读状态
	humanStatus := state
	cmd2 := exec.Command("docker", "inspect", "-f", `{{.State.Status}} ({{.State.ExitCode}}) {{.State.Error}}`, containerIDOrName)
	if out2, err := cmd2.CombinedOutput(); err == nil {
		s := strings.TrimSpace(string(out2))
		if s != "" {
			humanStatus = s
		}
	}

	// 容器只有在 state 为 "running" 时才算真正运行中
	// restarting 状态下 .State.Running 可能为 true（Docker 正在尝试重启），但容器并未正常工作
	running := state == "running"

	return ContainerDetail{
		ID:      truncateID(fullID),
		Name:    name,
		State:   state,
		Status:  humanStatus,
		Image:   image,
		Ports:   ports,
		Running: running,
	}, nil
}

// truncateID 截取容器 ID 为前 12 位
func truncateID(id string) string {
	if len(id) > 12 {
		return id[:12]
	}
	return id
}

// resolveComposePathForCollector 解析 compose 路径
func resolveComposePathForCollector(composePath string) (string, string, error) {
	if composePath == "" {
		return "", "", fmt.Errorf("no compose path configured")
	}

	// 如果是文件，直接返回
	if info, err := os.Stat(composePath); err == nil && !info.IsDir() {
		dir := filepath.Dir(composePath)
		return composePath, dir, nil
	}

	// 如果是目录，查找 compose 文件
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

// getDockerComposeCmd 返回可用的 docker compose 命令
func getDockerComposeCmd() string {
	if _, err := exec.LookPath("docker"); err == nil {
		// 检查 docker compose 是否可用
		cmd := exec.Command("docker", "compose", "version")
		if err := cmd.Run(); err == nil {
			return "docker"
		}
	}
	return "docker-compose"
}

func readPIDFile(path string) int {
	data, err := readFile(path)
	if err != nil {
		return 0
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil {
		return 0
	}
	return pid
}

func isPortListening(port int) bool {
	conn, err := net.Dial("tcp", ":"+strconv.Itoa(port))
	if err != nil {
		return false
	}
	conn.Close()
	return true
}

func findProcessByPath(path string) int {
	candidates := resolvePathCandidates(path, "")
	
	for _, candidate := range candidates {
		keywords := extractKeywords(candidate)
		for _, keyword := range keywords {
			if pid := grepProcess(keyword); pid > 0 {
				return pid
			}
		}
	}
	
	keywords := extractKeywords(path)
	for _, keyword := range keywords {
		if pid := grepProcess(keyword); pid > 0 {
			return pid
		}
	}
	
	return 0
}

func findProcessByName(name string) int {
	keywords := extractKeywords(name)
	
	for _, keyword := range keywords {
		if pid := grepProcess(keyword); pid > 0 {
			return pid
		}
	}
	
	return 0
}

func findProcessByStartCmd(startCmd string, username string) int {
	possiblePaths := resolvePathCandidates(startCmd, username)
	log.Printf("[DEBUG] findProcessByStartCmd: startCmd=%s, username=%s, possiblePaths=%v", startCmd, username, possiblePaths)
	
	// 存储所有要检测的关键字
	var keywords []string
	
	for _, scriptPath := range possiblePaths {
		if scriptPath == "" {
			log.Printf("[DEBUG] Skipping empty path")
			continue
		}
		
		// 检查文件是否存在
		info, err := os.Stat(scriptPath)
		if err != nil {
			log.Printf("[DEBUG] Path not found: %s, error: %v", scriptPath, err)
			continue
		}
		
		log.Printf("[DEBUG] Found existing path: %s, isDir=%v", scriptPath, info.IsDir())
		
		// 如果是脚本文件，读取内容提取关键字
		if strings.HasSuffix(scriptPath, ".sh") || strings.HasSuffix(scriptPath, ".py") || strings.HasSuffix(scriptPath, ".bat") {
			content, err := os.ReadFile(scriptPath)
			if err != nil {
				log.Printf("[DEBUG] Cannot read script %s: %v", scriptPath, err)
				continue
			}
			
			log.Printf("[DEBUG] Reading script: %s, content length=%d", scriptPath, len(content))
			log.Printf("[DEBUG] Script content: %s", string(content))
			
			// 从脚本内容中提取所有 .jar 文件名（优先使用）
			contentStr := string(content)
			jarRegex := regexp.MustCompile(`[a-zA-Z0-9_\-\.]+?\.jar`)
			jarMatches := jarRegex.FindAllString(contentStr, -1)
			log.Printf("[DEBUG] Found %d jar matches in script", len(jarMatches))
			for _, jarName := range jarMatches {
				if len(jarName) > 5 {
					keywords = append(keywords, jarName)
					log.Printf("[DEBUG] Found jar in script: %s", jarName)
				}
			}
			
			// 如果没有找到 jar 文件，从可执行命令行中提取有意义的关键字
			if len(jarMatches) == 0 {
				for _, line := range strings.Split(contentStr, "\n") {
					line = strings.TrimSpace(line)
					if line == "" || strings.HasPrefix(line, "#") {
						continue
					}
					
					cleanLine := strings.TrimPrefix(line, "./")
					cleanLine = strings.TrimSpace(cleanLine)
					
					if strings.Contains(cleanLine, "java") || 
					   strings.Contains(cleanLine, "python") ||
					   strings.Contains(cleanLine, "node") {
						log.Printf("[DEBUG] Found executable line in script: %s", cleanLine)
						execPaths := extractExecutablesFromCmd(cleanLine)
						for _, execPath := range execPaths {
							baseName := filepath.Base(execPath)
							// 过滤掉无用的关键字
							if len(baseName) > 5 && !isUselessKeyword(baseName) {
								keywords = append(keywords, baseName)
								log.Printf("[DEBUG] Extracted meaningful executable basename: %s", baseName)
							}
						}
					}
				}
			}
			
			// 找到第一个有效脚本后就停止搜索其他路径
			break
		} else {
			// 如果不是脚本文件，直接用文件名检测
			baseName := filepath.Base(scriptPath)
			if len(baseName) > 5 && !isUselessKeyword(baseName) {
				keywords = append(keywords, baseName)
			}
			break
		}
	}
	
	// 也从 startCmd 本身提取可执行文件（但过滤掉无用的）
	if len(keywords) == 0 {
		execPaths := extractExecutablesFromCmd(startCmd)
		for _, execPath := range execPaths {
			baseName := filepath.Base(execPath)
			if len(baseName) > 5 && !isUselessKeyword(baseName) {
				keywords = append(keywords, baseName)
			}
		}
	}
	
	// 去重并检测
	seen := make(map[string]bool)
	log.Printf("[DEBUG] All keywords to search: %v", keywords)
	for _, keyword := range keywords {
		if seen[keyword] {
			continue
		}
		seen[keyword] = true
		
		if pid := findProcessByCmdline(keyword); pid > 0 {
			log.Printf("[DEBUG] Found process by keyword '%s': PID=%d", keyword, pid)
			return pid
		}
	}
	
	log.Printf("[DEBUG] No process found for startCmd: %s", startCmd)
	return 0
}

// isUselessKeyword 判断关键字是否是无用的（太通用或无意义）
func isUselessKeyword(keyword string) bool {
	uselessKeywords := map[string]bool{
		"start": true, "stop": true, "restart": true,
		"nohup": true, "java": true, "python": true, "node": true,
		"bash": true, "sh": true, "cmd": true,
		"server": true, "client": true, "master": true, "slave": true,
		"$mypath": true, "$path": true,
	}
	
	if uselessKeywords[strings.ToLower(keyword)] {
		return true
	}
	
	// 过滤掉太通用的关键字（少于6个字符，且不含特殊后缀）
	if len(keyword) < 6 && !strings.HasSuffix(keyword, ".jar") && !strings.HasSuffix(keyword, ".py") {
		return true
	}
	
	return false
}

func resolvePathCandidates(path string, username string) []string {
	if path == "" {
		return nil
	}
	
	// 如果是绝对路径，直接返回
	if strings.HasPrefix(path, "/") {
		return []string{path}
	}
	
	// 如果是 ~/ 开头，展开 ~
	if strings.HasPrefix(path, "~/") {
		var candidates []string
		
		// 清理 username（处理 "<nil>" 等情况）
		cleanUsername := strings.TrimSpace(username)
		if cleanUsername == "" || cleanUsername == "<nil>" || cleanUsername == "null" {
			cleanUsername = ""
		}
		
		// 收集所有可能的 home 目录
		var homeDirs []string
		
		// 1. 如果有 username，优先用它
		if cleanUsername != "" {
			homeDir := getHomeDirByUser(cleanUsername)
			if homeDir != "" {
				homeDirs = append(homeDirs, homeDir)
			}
			// 尝试常见的用户目录模式
			for _, pattern := range []string{
				"/home/" + cleanUsername,
				"/u01/" + cleanUsername,
				"/u02/" + cleanUsername,
			} {
				homeDirs = append(homeDirs, pattern)
			}
		}
		
		// 2. 当前用户的 home 目录
		if home, err := os.UserHomeDir(); err == nil && home != "" {
			homeDirs = append(homeDirs, home)
		}
		
		// 3. 常见的 home 目录（当 username 为空时使用）
		if cleanUsername == "" {
			for _, dir := range []string{
				"/home", "/root", "/u01", "/u02",
				"/home/isi", "/home/app", "/home/srmc",
				"/u01/isi", "/u01/app", "/u01/srmc",
			} {
				homeDirs = append(homeDirs, dir)
			}
		}
		
		// 4. 去重并生成候选路径
		seen := make(map[string]bool)
		for _, homeDir := range homeDirs {
			if homeDir == "" {
				continue
			}
			resolved := filepath.Join(homeDir, path[2:])
			if !seen[resolved] {
				seen[resolved] = true
				candidates = append(candidates, resolved)
			}
		}
		
		return candidates
	}
	
	// 相对路径，添加当前目录
	absPath, err := filepath.Abs(path)
	if err == nil {
		return []string{absPath}
	}
	
	return []string{path}
}

// getHomeDirByUser 根据用户名获取 home 目录
func getHomeDirByUser(username string) string {
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
		"/root",
	}
	
	for _, p := range commonPaths {
		if info, err := os.Stat(p); err == nil && info.IsDir() {
			return p
		}
	}
	
	return ""
}

func getHomeDirectories() []string {
	var homes []string
	
	// 添加当前用户的 home 目录
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		homes = append(homes, home)
	}
	
	// 从 /etc/passwd 获取所有用户的 home 目录
	if data, err := os.ReadFile("/etc/passwd"); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			fields := strings.Split(line, ":")
			if len(fields) >= 6 {
				homeDir := fields[5]
				if homeDir != "/" && len(homeDir) > 2 {
					homes = append(homes, homeDir)
				}
			}
		}
	}
	
	// 添加常见的目录
	commonDirs := []string{
		"/home", "/root", "/u01", "/u02", 
		"/opt", "/var", "/data", "/srv",
	}
	for _, dir := range commonDirs {
		homes = append(homes, dir)
	}
	
	// 去重
	seen := make(map[string]bool)
	var result []string
	for _, h := range homes {
		if !seen[h] {
			seen[h] = true
			result = append(result, h)
		}
	}
	
	return result
}

func extractExecutablesFromCmd(cmd string) []string {
	var executables []string
	
	cmd = strings.TrimSpace(cmd)
	if cmd == "" {
		return executables
	}
	
	parts := strings.Fields(cmd)
	for _, part := range parts {
		cleaned := strings.Trim(part, "\"'")
		
		if strings.HasSuffix(cleaned, ".jar") {
			executables = append(executables, cleaned)
			jarName := strings.TrimSuffix(filepath.Base(cleaned), ".jar")
			if len(jarName) > 3 {
				executables = append(executables, jarName)
			}
			// "java" 太通用，放到最后
		} else if strings.HasSuffix(cleaned, ".py") {
			executables = append(executables, cleaned)
			pyName := strings.TrimSuffix(filepath.Base(cleaned), ".py")
			if len(pyName) > 3 {
				executables = append(executables, pyName)
			}
			// "python" / "python3" 太通用，放到最后
		} else if strings.HasSuffix(cleaned, ".js") || strings.HasSuffix(cleaned, ".ts") {
			executables = append(executables, cleaned)
			jsName := strings.TrimSuffix(filepath.Base(cleaned), filepath.Ext(cleaned))
			if len(jsName) > 3 {
				executables = append(executables, jsName)
			}
			// "node" 太通用，放到最后
		} else if strings.HasSuffix(cleaned, ".sh") {
			baseName := filepath.Base(cleaned)
			scriptName := strings.TrimSuffix(baseName, ".sh")
			if len(scriptName) > 3 {
				executables = append(executables, scriptName)
			}
		} else {
			if len(cleaned) > 3 && !strings.HasPrefix(cleaned, "-") {
				executables = append(executables, cleaned)
				executables = append(executables, filepath.Base(cleaned))
			}
		}
	}
	
	return executables
}

func extractKeywords(path string) []string {
	var keywords []string
	
	commonNames := map[string]bool{
		"server": true, "client": true, "bin": true, "app": true,
		"main": true, "service": true, "daemon": true, "tool": true,
		"node": true, "agent": true, "process": true, "command": true,
	}
	
	base := filepath.Base(path)
	parent := filepath.Base(filepath.Dir(path))
	
	if base != "." && base != "/" && len(base) > 2 {
		if !commonNames[strings.ToLower(base)] {
			keywords = append(keywords, base)
		}
	}
	
	if len(parent) > 2 {
		if !commonNames[strings.ToLower(parent)] {
			keywords = append(keywords, parent)
		}
	}
	
	return keywords
}

func grepProcess(keyword string) int {
	if len(keyword) < 3 {
		return 0
	}
	
	// Use the more accurate findProcessByCmdline function
	return findProcessByCmdline(keyword)
}

func verifyProcessMatch(pid int, keyword string) bool {
	cmdline, err := getProcessCmdline(pid)
	if err != nil || cmdline == "" {
		return false
	}
	
	return strings.Contains(strings.ToLower(cmdline), strings.ToLower(keyword))
}

func getContainerStatus(state string) string {
	switch state {
	case "running":
		return "Running"
	case "exited":
		return "Stopped"
	case "restarting":
		return "Restarting"
	case "paused":
		return "Paused"
	default:
		return "Unknown"
	}
}

func getLocalIP() string {
	if config.GlobalConfig.Agent.IP != "" {
		log.Printf("Using configured IP: %s", config.GlobalConfig.Agent.IP)
		return config.GlobalConfig.Agent.IP
	}
	
	addrs, _ := net.InterfaceAddrs()
	for _, addr := range addrs {
		if ipNet, ok := addr.(*net.IPNet); ok && !ipNet.IP.IsLoopback() && ipNet.IP.To4() != nil {
			return ipNet.IP.String()
		}
	}
	return "127.0.0.1"
}

func readFile(path string) ([]byte, error) {
	return os.ReadFile(path)
}