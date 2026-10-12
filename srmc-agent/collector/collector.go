package collector

import (
	"bytes"
	"fmt"
	"log"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
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
	ImageName   string `json:"image_name"`
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
	ID         string `json:"id"`          // 容器 ID（短）
	Name       string `json:"name"`        // 容器名称
	State      string `json:"state"`       // 容器状态（running/exited/dead/paused/restarting）
	Status     string `json:"status"`      // 人类可读状态（如 Up 2 hours、Exited (0) 5 minutes ago）
	Image      string `json:"image"`       // 镜像名称
	Ports      string `json:"ports"`       // 端口映射
	Running    bool   `json:"running"`     // 是否运行中
	ExitCode   int    `json:"exit_code"`   // 退出码（仅 exited 时有意义；-1 表示未知）
	OOMKilled  bool   `json:"oom_killed"`  // 是否因内存超限被 OOM Kill
	FinishedAt string `json:"finished_at"` // 最后退出时间（RFC3339；未退出为空）
	ExitReason string `json:"exit_reason"` // 退出原因（Docker State.Error，通常为空）
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
	Arch          string  `json:"arch"`
	CPUModel      string  `json:"cpu_model"`
	CPUCores      int     `json:"cpu_cores"`
	MemoryTotal   uint64  `json:"memory_total"`
}

var services []ServiceConfig
var lastMetrics SystemMetrics

// DetectDockerAPIVersion 启动时检测 Docker daemon 支持的 API 版本，
// 并设置到进程环境变量中。解决 Agent 容器预设的 DOCKER_API_VERSION
// 与目标 daemon 版本不匹配导致的 "client version X.XX is too new" 错误。
func DetectDockerAPIVersion() {
	// 先尝试读取当前预设版本
	currentVersion := os.Getenv("DOCKER_API_VERSION")

	// 通过 docker version --format '{{.Server.APIVersion}}' 获取 daemon 版本
	cmd := exec.Command("docker", "version", "--format", "{{.Server.APIVersion}}")
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()

	combined := stderr.String() + stdout.String()

	// 版本不匹配时 docker 会以非 0 退出并给出 daemon 最高支持版本，
	// 不能直接当成 "docker 不可用"，先尝试从错误里提取协商版本。
	if err != nil {
		re := regexp.MustCompile(`Maximum supported API version is ([0-9.]+)`)
		if match := re.FindStringSubmatch(combined); len(match) >= 2 {
			daemonMax := strings.TrimSpace(match[1])
			if daemonMax != "" && currentVersion != daemonMax {
				log.Printf("[INFO] Docker daemon max API version=%s (container preset=%s), overriding DOCKER_API_VERSION=%s",
					daemonMax, currentVersion, daemonMax)
				os.Setenv("DOCKER_API_VERSION", daemonMax)
			}
			return
		}
		// docker 命令真的不可用，跳过
		if currentVersion != "" {
			log.Printf("[WARN] docker command not available, keeping DOCKER_API_VERSION=%s", currentVersion)
		} else {
			log.Printf("[INFO] docker command not available, skipping API version detection")
		}
		return
	}

	daemonVersion := strings.TrimSpace(stdout.String())
	if daemonVersion == "" {
		// 输出里可能混有错误信息，尝试从 stderr+stdout 里提取
		re := regexp.MustCompile(`Maximum supported API version is ([0-9.]+)`)
		match := re.FindStringSubmatch(combined)
		if len(match) >= 2 {
			daemonVersion = match[1]
		}
	}

	if daemonVersion == "" {
		log.Printf("[WARN] could not detect Docker daemon API version, keeping DOCKER_API_VERSION=%s", currentVersion)
		return
	}

	if currentVersion != daemonVersion {
		log.Printf("[INFO] Docker API version: container=%s, daemon=%s, overriding DOCKER_API_VERSION=%s",
			currentVersion, daemonVersion, daemonVersion)
		os.Setenv("DOCKER_API_VERSION", daemonVersion)
	} else {
		log.Printf("[INFO] Docker API version: %s (matches daemon)", daemonVersion)
	}
}

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
		Arch:          runtime.GOARCH,
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
	output, err := runDockerCmd([]string{"docker", "network", "inspect", "-f", "{{range .IPAM.Config}}{{.Gateway}}{{end}}", "srmc_default"})
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
		// 容器不存在（未启动/已 rm）时，用配置里的 DockerName 构造占位行，
		// 让前端容器列表仍能显示该容器并设置运行类型（如 inactive）。
		// DockerName 是管理员在服务配置里手工填写的，无需推算，零猜测风险。
		status.Containers = []ContainerDetail{{
			Name:     svc.DockerName,
			State:    "created",
			Status:   "created",
			Image:    svc.ImageName,
			Running:  false,
			ExitCode: -1,
		}}
		return status
	}

	status.Containers = []ContainerDetail{container}

	if container.Running {
		status.Status = "Running"
	} else {
		status.Status = getContainerStatus(container.State)
	}

	// 采集容器创建时间作为 RunningSince
	output2, _ := runDockerCmd([]string{"docker", "inspect", "-f", "{{.Created}}", svc.DockerName})
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

	log.Printf("[DEBUG] collectComposeStatus: service=%s, dockerName=%s, composePath=%s", svc.ServiceID, svc.DockerName, svc.ComposePath)

	// 方式一（优先）：用 DockerName 精确检测。docker inspect 只需要 Docker API，
	// 不依赖 compose 文件路径，不受 Agent 容器目录挂载限制。
	// 注意：inspect 失败不直接判 Stopped，而是回退到方式二（compose label 过滤），
	// 两种方式互为兜底，避免单一检测手段在个别环境异常时误报停止。
	if svc.DockerName != "" {
		container, err := inspectContainer(svc.DockerName)
		if err == nil {
			status.Containers = []ContainerDetail{container}
			if container.Running {
				status.Status = "Running"
			} else {
				status.Status = "Stopped"
			}
			return status
		}
		log.Printf("[DEBUG] collectComposeStatus: inspect %s failed (%v), fallback to compose label filter", svc.DockerName, err)
		// 回退继续走下面的 compose_path label 过滤
	}

	// 方式二：通过 compose 文件路径的 config_files label 过滤（compose V2 启动的容器自带该 label）。
	// docker ps --format 一次拿全字段，不依赖 inspect。
	if svc.ComposePath == "" {
		log.Printf("[DEBUG] collectComposeStatus: no docker_name and no compose_path for service %s", svc.ServiceID)
		if svc.DockerName != "" {
			// DockerName inspect 失败且无 compose_path 兜底
			status.Status = "Stopped"
			status.Containers = []ContainerDetail{{
				ID: svc.DockerName, Name: svc.DockerName, State: "unknown",
				Status: "inspect failed", Running: false,
			}}
		}
		return status
	}

	// 解析 compose 路径（支持目录和文件）
	composeFile, workDir, err := resolveComposePathForCollector(svc.ComposePath)
	if err != nil {
		log.Printf("[DEBUG] collectComposeStatus: resolve error: %v (path=%s)", err, svc.ComposePath)
		status.Status = "Stopped"
		return status
	}

	log.Printf("[DEBUG] collectComposeStatus: composeFile=%s, workDir=%s", composeFile, workDir)

	// 直接用 docker ps --filter --format 一次拿全所有容器信息
	// 不调用 docker compose ps，避免 yml 解析（exit 15）和项目名匹配问题
	// 用 compose 文件绝对路径做过滤，全局唯一，不会重名误匹配
	containers, err := listContainersByComposeFile(composeFile)
	if err != nil {
		log.Printf("[DEBUG] collectComposeStatus: list containers error: %v", err)
		status.Status = "Stopped"
		return status
	}

	log.Printf("[DEBUG] collectComposeStatus: found %d containers", len(containers))

	// 补充"已定义但未创建容器"的服务：整个 Compose 从未启动（或已 down）时，
	// docker ps -a 一个容器都查不到，前端容器列表为空，无法设置运行类型。
	// 用 docker-compose config 解析出定义的服务名，补占位行。
	containers = appendDefinedComposeServices(composeFile, containers)

	status.Containers = containers
	totalCount := len(containers)
	runningCount := 0
	for _, c := range containers {
		if c.Running {
			runningCount++
		}
	}

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

// appendDefinedComposeServices 解析 compose 文件中定义的服务，把尚无对应容器的服务
// 以占位行（state=created）补进列表，使前端在服务未启动时也能设置运行类型。
//
// 容器名解析规则：
//   - YAML 显式写了 container_name → 直接使用（准确）
//   - 未写 → 按 compose 默认规则 <项目名>-<服务名>-1 推算
//
// 解析失败时静默返回原列表，不影响既有采集逻辑。
func appendDefinedComposeServices(composeFile string, existing []ContainerDetail) []ContainerDetail {
	// 已有容器名集合，用于去重
	known := make(map[string]bool, len(existing))
	for _, c := range existing {
		known[c.Name] = true
	}

	// docker-compose config 输出解析后的完整配置（含 container_name 与项目名）
	out, err := runDockerCmd([]string{"docker-compose", "-f", composeFile, "config"})
	if err != nil {
		// 兼容 docker compose（v2 插件形式）
		out, err = runDockerCmd([]string{"docker", "compose", "-f", composeFile, "config"})
		if err != nil {
			log.Printf("[DEBUG] appendDefinedComposeServices: config failed: %v", err)
			return existing
		}
	}

	projectName := ""
	serviceNames := []string{}
	containerNames := map[string]string{} // service -> container_name（仅显式声明）

	lines := strings.Split(string(out), "\n")
	inServices := false
	curService := ""
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		indent := len(line) - len(strings.TrimLeft(line, " "))

		// 顶层 name: <项目名>
		if indent == 0 && strings.HasPrefix(trimmed, "name:") {
			projectName = strings.TrimSpace(strings.TrimPrefix(trimmed, "name:"))
			continue
		}
		// 顶层 services:
		if indent == 0 && trimmed == "services:" {
			inServices = true
			continue
		}
		// 离开 services 段（其他顶层键）
		if indent == 0 && inServices {
			inServices = false
			continue
		}
		if !inServices {
			continue
		}
		// 二级缩进：服务名
		if indent == 2 && strings.HasSuffix(trimmed, ":") {
			curService = strings.TrimSuffix(trimmed, ":")
			serviceNames = append(serviceNames, curService)
			continue
		}
		// 三级缩进：container_name
		if indent >= 4 && curService != "" && strings.HasPrefix(trimmed, "container_name:") {
			containerNames[curService] = strings.TrimSpace(strings.TrimPrefix(trimmed, "container_name:"))
		}
	}

	if len(serviceNames) == 0 {
		return existing
	}

	added := 0
	for _, svc := range serviceNames {
		name := containerNames[svc]
		if name == "" {
			// 未显式声明 container_name，按 compose 默认规则推算
			if projectName == "" {
				projectName = filepath.Base(filepath.Dir(composeFile))
			}
			name = fmt.Sprintf("%s-%s-1", projectName, svc)
		}
		if known[name] {
			continue
		}
		known[name] = true
		existing = append(existing, ContainerDetail{
			Name:     name,
			State:    "created",
			Status:   "created",
			Running:  false,
			ExitCode: -1,
		})
		added++
	}

	if added > 0 {
		log.Printf("[DEBUG] appendDefinedComposeServices: added %d defined-but-not-created containers", added)
	}
	return existing
}

// listContainersByComposeFile 用 docker ps --filter --format 一次拿全所有容器信息。
// 通过 compose 文件的绝对路径做 label 过滤（com.docker.compose.project.config_files），
// 全局唯一，不受目录同名影响。不调用 docker compose ps，绕过 yml 解析和项目名匹配问题。
// 输出格式用管道符分隔字段，避免容器名/状态里包含空格导致解析错误。
func listContainersByComposeFile(composeFile string) ([]ContainerDetail, error) {
	// docker ps --format 模板：
	//   ID|Name|State|Image|Ports|RunningFor|ExitCode
	// - .ID: 短 ID（12 位）
	// - .Names: 容器名（多个用逗号分隔，但 compose 容器一般只有一个名）
	// - .State: 容器状态（running/exited/paused/restarting/dead）
	// - .Image: 镜像名
	// - .Ports: 端口映射（与 docker ps 显示一致，如 0.0.0.0:9013->8080/tcp）
	// - .RunningFor: 人类可读的运行时间（如 "Up 2 hours"），用于 Status 字段
	// - .Label "com.docker.compose.project.config_files": 用于按 compose 文件过滤
	// 注意：.Ports 在容器未运行时可能为空，需要单独处理
	// exit_code 不在 docker ps 中，需对非 running 容器单独 inspect 获取
	format := "{{.ID}}|{{.Names}}|{{.State}}|{{.Image}}|{{.Ports}}|{{.RunningFor}}"
	filter := fmt.Sprintf("label=com.docker.compose.project.config_files=%s", composeFile)

	output, err := runDockerCmd([]string{"docker", "ps", "-a", "--filter", filter, "--format", format})
	if err != nil {
		return nil, fmt.Errorf("docker ps failed: %v, output: %s", err, string(output))
	}

	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	containers := make([]ContainerDetail, 0, len(lines))
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		// 跳过 docker CLI 混入 stdout 的 warning/log 行
		// 例如: time="..." level=warning msg="The \"docker_user_uid\" variable is not set..."
		if isDockerCLILogLine(line) {
			log.Printf("[DEBUG] listContainersByComposeFile: skip docker CLI log line: %s", truncateStr(line, 120))
			continue
		}
		parts := strings.SplitN(line, "|", 6)
		if len(parts) < 6 {
			log.Printf("[DEBUG] listContainersByComposeFile: unexpected line: %s", truncateStr(line, 120))
			continue
		}

		id := strings.TrimSpace(parts[0])
		name := strings.TrimSpace(parts[1])
		state := strings.TrimSpace(parts[2])
		image := parts[3]
		ports := parts[4]
		runningFor := parts[5]

		// 严格校验容器 ID 必须是十六进制，防止 warning/错误文本被当成容器
		if !isHexContainerID(id) {
			log.Printf("[DEBUG] listContainersByComposeFile: skip non-container id=%q line=%s", id, truncateStr(line, 120))
			continue
		}

		// 人类可读状态：运行中显示运行时间，已停止显示状态
		humanStatus := state
		if state == "running" {
			if runningFor != "" {
				humanStatus = "Up " + runningFor
			}
		} else {
			// 已停止的容器，状态可能为 exited/paused/dead
			humanStatus = state
		}

		// 只有 state == "running" 才算真正运行中
		// restarting 状态不算运行中（容器正在尝试重启，但未正常工作）
		running := state == "running"

		// 退出详情：仅对非 running 容器查询（running 容器无退出码，置 -1）
		// 一次 inspect 同时拿到 ExitCode / OOMKilled / FinishedAt / Error，不额外增加轮询
		exitCode := -1
		oomKilled := false
		finishedAt := ""
		exitReason := ""
		if !running {
			exitCode, oomKilled, finishedAt, exitReason = getContainerExitDetail(id)
		}

		containers = append(containers, ContainerDetail{
			ID:         id,
			Name:       name,
			State:      state,
			Status:     humanStatus,
			Image:      image,
			Ports:      ports,
			Running:    running,
			ExitCode:   exitCode,
			OOMKilled:  oomKilled,
			FinishedAt: finishedAt,
			ExitReason: exitReason,
		})
	}

	return containers, nil
}

// getContainerExitDetail 一次 inspect 获取退出详情（退出码/OOMKilled/最后退出时间/退出原因）。
// 复用同一次 docker inspect，不额外增加轮询；查询失败时返回零值（exit_code=-1）。
func getContainerExitDetail(containerIDOrName string) (exitCode int, oomKilled bool, finishedAt, exitReason string) {
	exitCode = -1
	out, err := runDockerCmd([]string{
		"docker", "inspect", "-f",
		"{{.State.ExitCode}}|{{.State.OOMKilled}}|{{.State.FinishedAt}}|{{.State.Error}}",
		containerIDOrName,
	})
	if err != nil {
		return
	}
	s := strings.TrimSpace(stripDockerCLILogLines(string(out)))
	if s == "" {
		return
	}
	parts := strings.SplitN(s, "|", 4)
	if len(parts) < 4 {
		return
	}
	if code, convErr := strconv.Atoi(strings.TrimSpace(parts[0])); convErr == nil {
		exitCode = code
	}
	oomKilled = strings.TrimSpace(parts[1]) == "true"
	finishedAt = strings.TrimSpace(parts[2])
	exitReason = strings.TrimSpace(parts[3])
	return
}

// runDockerCmd 执行 docker 命令，当遇到 API 版本不匹配错误时自动降级重试。
// 成功时只返回纯净的 stdout。
func runDockerCmd(args []string) ([]byte, error) {
	return execWithVersionFallback(args, "")
}

// inspectContainer 通过 docker inspect 获取容器详细信息
func inspectContainer(containerIDOrName string) (ContainerDetail, error) {
	// 使用 Go template 一次性获取所有需要的字段，避免多次调用 docker inspect
	// 端口映射格式: 遍历 NetworkSettings.Ports (map[port][]PortBinding)
	// 容器端口是 map 的 key（如 "8080/tcp"），HostPort 是物理机端口（如 "9013"）
	// 显示格式与 docker ps 一致：物理机端口->容器端口，如 9013->8080/tcp
	format := `{{.Id}}|{{.Name}}|{{.State.Status}}|{{.State.Running}}|{{.Config.Image}}|{{range $port, $bindings := .NetworkSettings.Ports}}{{range $bindings}}{{.HostPort}}->{{$port}},{{end}}{{end}}|{{.State.Status}}`
	out, err := runDockerCmd([]string{"docker", "inspect", "-f", format, containerIDOrName})
	if err != nil {
		return ContainerDetail{}, err
	}

	// 剥离混入 stdout 的 docker CLI warning/log 行，只保留模板输出行
	cleanOut := stripDockerCLILogLines(string(out))
	parts := strings.Split(strings.TrimSpace(cleanOut), "|")
	if len(parts) < 6 {
		return ContainerDetail{}, fmt.Errorf("unexpected inspect output: %s", truncateStr(cleanOut, 160))
	}

	fullID := strings.TrimSpace(parts[0])
	// 严格校验容器 ID，防止 warning 文本污染导致字段错位
	if !isHexContainerID(fullID) {
		return ContainerDetail{}, fmt.Errorf("invalid container id in inspect output: %q", truncateStr(cleanOut, 160))
	}
	name := strings.TrimPrefix(strings.TrimSpace(parts[1]), "/") // 容器名前缀有 /
	state := strings.TrimSpace(parts[2])
	image := strings.TrimSpace(parts[4])
	ports := strings.TrimSpace(parts[5])

	// 人类可读状态
	humanStatus := state
	out2, err2 := runDockerCmd([]string{"docker", "inspect", "-f", `{{.State.Status}} ({{.State.ExitCode}}) {{.State.Error}}`, containerIDOrName})
	if err2 == nil {
		s := strings.TrimSpace(stripDockerCLILogLines(string(out2)))
		if s != "" {
			humanStatus = s
		}
	}

	// 容器只有在 state 为 "running" 时才算真正运行中
	// restarting 状态下 .State.Running 可能为 true（Docker 正在尝试重启），但容器并未正常工作
	running := state == "running"

	// 退出详情：仅对非 running 容器查询（running 容器无退出码，置 -1）
	// 一次 inspect 同时拿到 ExitCode / OOMKilled / FinishedAt / Error，不额外增加轮询
	exitCode := -1
	oomKilled := false
	finishedAt := ""
	exitReason := ""
	if !running {
		exitCode, oomKilled, finishedAt, exitReason = getContainerExitDetail(containerIDOrName)
	}

	return ContainerDetail{
		ID:         truncateID(fullID),
		Name:       name,
		State:      state,
		Status:     humanStatus,
		Image:      image,
		Ports:      ports,
		Running:    running,
		ExitCode:   exitCode,
		OOMKilled:  oomKilled,
		FinishedAt: finishedAt,
		ExitReason: exitReason,
	}, nil
}

// truncateID 截取容器 ID 为前 12 位
func truncateID(id string) string {
	if len(id) > 12 {
		return id[:12]
	}
	return id
}

// isHexContainerID 判断字符串是否为合法的 Docker 容器 ID（十六进制，12~64 位）
func isHexContainerID(s string) bool {
	s = strings.TrimSpace(s)
	if len(s) < 12 || len(s) > 64 {
		return false
	}
	for _, c := range s {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')) {
			return false
		}
	}
	return true
}

// isDockerCLILogLine 判断一行是否为 docker CLI 的日志输出（warning/error/info）。
// 这类输出本应在 stderr，但可能混入 stdout，例如：
//
//	time="2026-09-07T00:31:22Z" level=warning msg="The \"docker_user_uid\" variable is not set..."
func isDockerCLILogLine(line string) bool {
	trimmed := strings.TrimSpace(line)
	if !strings.HasPrefix(trimmed, `time="`) {
		return false
	}
	return strings.Contains(trimmed, "level=warning") ||
		strings.Contains(trimmed, "level=error") ||
		strings.Contains(trimmed, "level=info")
}

// stripDockerCLILogLines 移除多行输出中的 docker CLI 日志行，返回纯净内容
func stripDockerCLILogLines(s string) string {
	var kept []string
	for _, l := range strings.Split(s, "\n") {
		if isDockerCLILogLine(l) {
			continue
		}
		kept = append(kept, l)
	}
	return strings.Join(kept, "\n")
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

// runComposeCmd 执行 docker compose 命令，自动在 docker compose (V2) 和 docker-compose (V1) 之间切换。
// 同时处理 Docker API 版本不匹配问题（如 client version 1.44 vs daemon 1.43）。
// 不指定 -p 项目名：让 compose 使用 yml 里的 name 字段（用户已为每个 yml 配置唯一 name）。
// 策略：先试 V2，V2 失败（任何原因）都尝试 V1，V1 也失败才返回错误。
// 这样能兼容各种环境：只有 V2、只有 V1、两者都有、yaml 解析差异等。
func runComposeCmd(composeFile, workDir string, composeArgs ...string) ([]byte, error) {
	var v2Err, v1Err error
	var v2Output []byte

	// 尝试 docker compose (V2 插件模式)
	if _, err := exec.LookPath("docker"); err == nil {
		fullArgs := append([]string{"docker", "compose", "-f", composeFile}, composeArgs...)
		v2Output, v2Err = execWithVersionFallback(fullArgs, workDir)
		if v2Err == nil {
			return v2Output, nil
		}
		// V2 失败，记录错误，继续尝试 V1
		log.Printf("[DEBUG] runComposeCmd V2 failed: %v, errStr=%s", v2Err, truncateStr(string(v2Output), 200))
	}

	// 尝试 docker-compose (V1 独立命令)
	// 无论 V2 失败原因是什么（插件不存在、yaml 解析错误、API 版本问题等），都尝试 V1
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
		log.Printf("[DEBUG] runComposeCmd V1 failed: %v, errStr=%s", v1Err, truncateStr(string(output), 200))
	}

	// 两个都失败，返回更详细的错误
	if v2Err != nil && v1Err != nil {
		return v2Output, fmt.Errorf("docker compose (V2) failed: %v; docker-compose (V1) failed: %v", v2Err, v1Err)
	}
	if v2Err != nil {
		return v2Output, fmt.Errorf("docker compose (V2) failed: %v; docker-compose (V1) not installed", v2Err)
	}
	return nil, fmt.Errorf("docker-compose (V1) failed: %v; docker compose (V2) not installed", v1Err)
}

func truncateStr(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}

// execWithVersionFallback 执行 docker 命令，当遇到 API 版本不匹配错误时自动降级重试。
// 成功时只返回纯净的 stdout（避免 stderr 的 warning 污染输出，例如
// "docker_user_uid variable is not set" 会被误当成容器 ID）。
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

	// 合并 stderr+stdout 用于错误文本检测（warning 可能出现在 stderr）
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
			
			// ============ 核心修复：先解析并展开 bash 变量 ============
			// 例如脚本中有：
			//   app=casia-delete-es-event-data-month
			//   nohup java -jar lib/$app.jar ...
			// 展开后变成：
			//   nohup java -jar lib/casia-delete-es-event-data-month.jar ...
			contentStr := string(content)
			bashVars := parseBashVariables(contentStr)
			log.Printf("[DEBUG] Parsed bash variables: %v", bashVars)
			expandedContent := expandBashVariables(contentStr, bashVars)
			log.Printf("[DEBUG] Expanded script content: %s", expandedContent)
			
			// 只从展开后的内容提取 jar 名（避免 $app.jar 中的 app.jar 被误匹配）
			var jarMatches []string
			jarRegex := regexp.MustCompile(`[a-zA-Z0-9_\-\.]+?\.jar`)
			jarMatches = append(jarMatches, jarRegex.FindAllString(expandedContent, -1)...)
			log.Printf("[DEBUG] Found %d jar matches (expanded only)", len(jarMatches))
			seen := make(map[string]bool)
			for _, jarName := range jarMatches {
				if len(jarName) > 5 && !seen[jarName] {
					seen[jarName] = true
					keywords = append(keywords, jarName)
					log.Printf("[DEBUG] Found jar in script: %s", jarName)
				}
			}
			
			// 如果没有找到 jar 文件，从脚本中提取原生二进制名
			if len(jarMatches) == 0 {
				for _, line := range strings.Split(expandedContent, "\n") {
					line = strings.TrimSpace(line)
					if line == "" || strings.HasPrefix(line, "#") {
						continue
					}

					cleanLine := strings.TrimPrefix(line, "./")
					cleanLine = strings.TrimSpace(cleanLine)

					// 去掉 nohup 前缀
					if strings.HasPrefix(cleanLine, "nohup ") {
						cleanLine = strings.TrimPrefix(cleanLine, "nohup ")
						cleanLine = strings.TrimSpace(cleanLine)
					}

					// 跳过非启动命令行
					if strings.HasPrefix(cleanLine, "cd ") ||
						strings.Contains(cleanLine, "=") && !strings.Contains(cleanLine, "java") ||
						strings.HasPrefix(cleanLine, "if ") ||
						strings.HasPrefix(cleanLine, "fi") ||
						strings.HasPrefix(cleanLine, "echo ") ||
						strings.HasPrefix(cleanLine, "exit ") ||
						strings.HasPrefix(cleanLine, "export ") ||
						strings.HasPrefix(cleanLine, "pid=") ||
						strings.HasPrefix(cleanLine, "-") {
						continue
					}

					log.Printf("[DEBUG] Found executable line in script: %s", cleanLine)

					// 提取原生二进制名（如 bin/elasticsearch, bin/mysqld, redis-server, nginx）
					execPaths := extractExecutablesFromCmd(cleanLine)
					for _, execPath := range execPaths {
						baseName := filepath.Base(execPath)
						if !isUselessKeyword(baseName) {
							keywords = append(keywords, baseName)
							log.Printf("[DEBUG] Extracted meaningful executable basename: %s", baseName)
						}
					}

					// 特殊处理：Tomcat 等通过 startup.sh 启动但实际进程是 java -Dcatalina...
					// 从脚本路径或内容中识别 catalina/tomcat 关键字
					if strings.Contains(strings.ToLower(expandedContent), "catalina") {
						keywords = append(keywords, "catalina")
						log.Printf("[DEBUG] Detected Tomcat-like service, adding keyword: catalina")
					}
					if strings.Contains(strings.ToLower(expandedContent), "solr") {
						keywords = append(keywords, "solr")
						log.Printf("[DEBUG] Detected Solr-like service, adding keyword: solr")
					}
				}
			}
			
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
		"nohup": true, "java": true, "python": true, "python3": true, "node": true,
		"bash": true, "sh": true, "cmd": true, "bin": true,
		"server": true, "client": true, "master": true, "slave": true,
		"$mypath": true, "$path": true, "app": true, "lib": true,
		"conf": true, "config": true, "log": true, "logs": true,
		"daemon": true, "agent": true, "main": true, "run": true,
	}

	lower := strings.ToLower(keyword)
	if uselessKeywords[lower] {
		return true
	}

	// 过滤掉太短的关键字（少于3个字符）
	if len(keyword) < 3 {
		return true
	}

	return false
}

// parseBashVariables 解析 bash 脚本中的变量赋值
// 支持：export NAME=value / NAME="value" / NAME='value' / NAME=value
// 不支持：跨引号、命令替换、嵌套等复杂 bash 语法（覆盖 95% 常用场景）
func parseBashVariables(content string) map[string]string {
	vars := make(map[string]string)
	for _, line := range strings.Split(content, "\n") {
		line = strings.TrimSpace(line)
		// 跳过注释、空行和管道命令
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		// 去掉 "export " 前缀（可选）
		line = strings.TrimPrefix(line, "export ")
		// 匹配 NAME=value 格式
		eqIdx := strings.IndexByte(line, '=')
		if eqIdx <= 0 {
			continue
		}
		name := strings.TrimSpace(line[:eqIdx])
		value := strings.TrimSpace(line[eqIdx+1:])
		// 简单校验 name 是合法标识符
		if !regexp.MustCompile(`^[a-zA-Z_][a-zA-Z0-9_]*$`).MatchString(name) {
			continue
		}
		// 去掉外层引号（双引号或单引号）
		if len(value) >= 2 {
			if (value[0] == '"' && value[len(value)-1] == '"') ||
				(value[0] == '\'' && value[len(value)-1] == '\'') {
				value = value[1 : len(value)-1]
			}
		}
		// 去掉行尾的分号
		value = strings.TrimSuffix(value, ";")
		if name != "" {
			vars[name] = value
		}
	}
	return vars
}

// expandBashVariables 用变量表展开字符串中的 $NAME 和 ${NAME}
// 已定义的变量替换为其值，未定义的变量替换为空字符串（与 bash 默认行为一致）
func expandBashVariables(content string, vars map[string]string) string {
	result := content
	// 先处理 ${NAME} 形式
	for name, value := range vars {
		result = strings.ReplaceAll(result, "${"+name+"}", value)
	}
	// 再处理 $NAME 形式 - 简单替换即可
	for name, value := range vars {
		result = strings.ReplaceAll(result, "$"+name, value)
	}
	// 最后处理未定义的 $VAR：替换为空字符串（与 bash 默认行为一致）
	// 例如 $app.jar → .jar，避免被正则误匹配为 app.jar
	undefinedVarRegex := regexp.MustCompile(`\$([a-zA-Z_][a-zA-Z0-9_]*)`)
	result = undefinedVarRegex.ReplaceAllStringFunc(result, func(match string) string {
		varName := match[1:] // 去掉 $ 前缀
		if _, defined := vars[varName]; defined {
			return match // 已定义的变量保留（已在上面替换过）
		}
		return "" // 未定义的变量替换为空
	})
	return result
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