package transport

import (
	"encoding/json"
	"fmt"
	"github.com/gorilla/websocket"
	"log"
	"net/url"
	"srmc-agent/config"
	"srmc-agent/collector"
	"srmc-agent/manager"
	"sync"
	"time"
)

type Message struct {
	Type      string                 `json:"type"`
	RequestID string                 `json:"request_id"`
	Timestamp float64                `json:"timestamp"`
	Data      map[string]interface{} `json:"data"`
}

// toString safely converts an interface{} to string, returning "" for nil
// (fmt.Sprintf("%v", nil) produces "<nil>" which causes false-positive checks)
func toString(v interface{}) string {
	if v == nil {
		return ""
	}
	return fmt.Sprintf("%v", v)
}

type Registration struct {
	UUID        string `json:"uuid"`
	Hostname    string `json:"hostname"`
	IP          string `json:"ip"`
	OS          string `json:"os"`
	Kernel      string `json:"kernel"`
	Arch        string `json:"arch"`
	CPUModel    string `json:"cpu_model"`
	CPUCores    int    `json:"cpu_cores"`
	MemoryTotal uint64 `json:"memory_total"`
	AgentVersion string `json:"agent_version"`
	Capabilities []string `json:"capabilities"`
	Tags        []string `json:"tags"`
	// 部署元信息（供后端批量更新下发时使用）
	DeployMethod  string `json:"deploy_method"`
	DeployDir     string `json:"deploy_dir"`
	ComposeFile   string `json:"compose_file"`
	BinaryPath    string `json:"binary_path"`
	ServiceName   string `json:"service_name"`
	UpdatesDir    string `json:"updates_dir"`
	BackupDir     string `json:"backup_dir"`
}

type Heartbeat struct {
	System          collector.SystemMetrics      `json:"system"`
	Services        []collector.ServiceStatus    `json:"services"`
	DockerContainers []ContainerStatus            `json:"docker_containers"`
	ComposeProjects []ComposeStatus               `json:"compose_projects"`
}

type ContainerStatus struct {
	ID      string `json:"id"`
	Name    string `json:"name"`
	Image   string `json:"image"`
	Status  string `json:"status"`
	Running bool   `json:"running"`
}

type ComposeStatus struct {
	Project string `json:"project"`
	Status  string `json:"status"`
	Running int    `json:"running"`
	Total   int    `json:"total"`
}

var conn *websocket.Conn
var reconnectCount int
var maxReconnectAttempts = 30
var reconnectDelay = time.Second

// 注册确认：后端收到 register 后会回 pull_services，收到即视为注册成功。
// 若超时未收到则重发 register，避免首次注册消息丢失导致长时间离线。
var registerAcked bool
var registerAckMu sync.Mutex

const (
	registerAckTimeout  = 10 * time.Second
	registerMaxAttempts = 6
)

func markRegisterAcked() {
	registerAckMu.Lock()
	registerAcked = true
	registerAckMu.Unlock()
}

func isRegisterAcked() bool {
	registerAckMu.Lock()
	defer registerAckMu.Unlock()
	return registerAcked
}

// SendRegistrationWithRetry 发送注册并在超时未收到后端响应时重发。
func SendRegistrationWithRetry() {
	registerAckMu.Lock()
	registerAcked = false
	registerAckMu.Unlock()

	for i := 1; i <= registerMaxAttempts; i++ {
		if err := SendRegistration(); err != nil {
			log.Printf("[REGISTER] send failed (attempt %d/%d): %v", i, registerMaxAttempts, err)
		} else {
			log.Printf("[REGISTER] sent (attempt %d/%d)", i, registerMaxAttempts)
		}

		deadline := time.Now().Add(registerAckTimeout)
		for time.Now().Before(deadline) {
			if isRegisterAcked() {
				log.Printf("[REGISTER] acknowledged by server")
				return
			}
			time.Sleep(500 * time.Millisecond)
		}
		log.Printf("[REGISTER] no ack within %v, retrying", registerAckTimeout)
	}
	log.Printf("[REGISTER] gave up after %d attempts, waiting for reconnect", registerMaxAttempts)
}

func Connect() error {
	u, _ := url.Parse(config.GlobalConfig.Server.URL)
	u.Path += config.AgentUUID

	header := make(map[string][]string)
	if config.GlobalConfig.Server.Token != "" {
		header["Authorization"] = []string{"Bearer " + config.GlobalConfig.Server.Token}
	}

	c, _, err := websocket.DefaultDialer.Dial(u.String(), header)
	if err != nil {
		return err
	}

	conn = c
	reconnectCount = 0
	reconnectDelay = time.Second

	go readLoop()

	return nil
}

func readLoop() {
	defer reconnect()

	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			log.Printf("Read error: %v", err)
			return
		}

		var msg Message
		if err := json.Unmarshal(message, &msg); err != nil {
			log.Printf("Failed to parse message: %v", err)
			continue
		}

		handleMessage(msg)
	}
}

func handleMessage(msg Message) {
	log.Printf("Received message: %s", msg.Type)

	switch msg.Type {
	case "pull_services":
		// 后端收到 register 后会下发 pull_services，视为注册确认
		markRegisterAcked()
		handlePullServices(msg)
	case "services":
		handleServices(msg)
	case "command":
		handleCommand(msg)
	case "config_update":
		log.Printf("Config update")
	case "update":
		handleUpdate(msg)
	}
}

func handlePullServices(msg Message) {
	log.Printf("Received pull_services command, requesting service list from server")
	
	pullMsg := Message{
		Type:      "pull_services",
		RequestID: msg.RequestID,
		Data:      map[string]interface{}{},
	}
	SendMessage(pullMsg)
}

func handleServices(msg Message) {
	log.Printf("Received services list from server")
	
	data := msg.Data
	servicesData, ok := data["services"].([]interface{})
	if !ok {
		log.Printf("No services data found")
		return
	}
	
	var serviceConfigs []collector.ServiceConfig
	for _, svcData := range servicesData {
		svcMap, ok := svcData.(map[string]interface{})
		if !ok {
			continue
		}
		
		port := 0
		if p, ok := svcMap["port"].(float64); ok {
			port = int(p)
		}
		
		serviceConfigs = append(serviceConfigs, collector.ServiceConfig{
		ServiceID:   toString(svcMap["service_id"]),
		Name:        toString(svcMap["name"]),
		Username:    toString(svcMap["username"]),
		DeployType:  toString(svcMap["deploy_type"]),
		PIDFile:     toString(svcMap["pid_file"]),
		Port:        port,
		HealthURL:   toString(svcMap["health_url"]),
		StartCmd:    toString(svcMap["start_cmd"]),
		StopCmd:     toString(svcMap["stop_cmd"]),
		RestartCmd:  toString(svcMap["restart_cmd"]),
		LogPath:     toString(svcMap["log_path"]),
		DockerName:  toString(svcMap["docker_name"]),
		ImageName:   toString(svcMap["image_name"]),
		ComposePath: toString(svcMap["compose_path"]),
	})
	}
	
	collector.UpdateServices(serviceConfigs)
	log.Printf("Updated %d services", len(serviceConfigs))
}

func handleCommand(msg Message) {
	serviceID := toString(msg.Data["service_id"])
	action := toString(msg.Data["action"])

	log.Printf("[COMMAND] Received command: service_id=%s, action=%s, deploy_type=%v, start_cmd=%v, username=%v",
		serviceID, action, msg.Data["deploy_type"], msg.Data["start_cmd"], msg.Data["username"])

	serviceConfig := manager.ServiceConfig{
		ServiceID:   serviceID,
		Username:    toString(msg.Data["username"]),
		DeployType:  toString(msg.Data["deploy_type"]),
		DockerName:  toString(msg.Data["docker_name"]),
		ComposePath: toString(msg.Data["compose_path"]),
		StartCmd:    toString(msg.Data["start_cmd"]),
		StopCmd:     toString(msg.Data["stop_cmd"]),
		RestartCmd:  toString(msg.Data["restart_cmd"]),
		LogPath:     toString(msg.Data["log_path"]),
	}

	switch action {
	case "start":
		result := manager.StartService(serviceConfig)
		response := Message{
			Type:      "command_result",
			RequestID: msg.RequestID,
			Data: map[string]interface{}{
				"service_id": serviceID,
				"action":     action,
				"success":    result.Success,
				"output":     result.Output,
				"error":      result.Error,
			},
		}
		SendMessage(response)
	case "stop":
		result := manager.StopService(serviceConfig)
		response := Message{
			Type:      "command_result",
			RequestID: msg.RequestID,
			Data: map[string]interface{}{
				"service_id": serviceID,
				"action":     action,
				"success":    result.Success,
				"output":     result.Output,
				"error":      result.Error,
			},
		}
		SendMessage(response)
	case "restart":
		result := manager.RestartService(serviceConfig)
		response := Message{
			Type:      "command_result",
			RequestID: msg.RequestID,
			Data: map[string]interface{}{
				"service_id": serviceID,
				"action":     action,
				"success":    result.Success,
				"output":     result.Output,
				"error":      result.Error,
			},
		}
		SendMessage(response)
	case "logs":
		go func() {
			err := manager.StreamLogs(serviceConfig, func(line manager.LogLine) {
				logMsg := Message{
					Type: "log_line",
					Data: map[string]interface{}{
						"service_id": line.ServiceID,
						"line":       line.Line,
						"timestamp":  line.Timestamp,
					},
				}
				SendMessage(logMsg)
			})
			if err != nil {
				log.Printf("Log streaming error: %v", err)
				response := Message{
					Type:      "command_result",
					RequestID: msg.RequestID,
					Data: map[string]interface{}{
						"service_id": serviceID,
						"action":     action,
						"success":    false,
						"error":      err.Error(),
					},
				}
				SendMessage(response)
			}
		}()
	default:
		response := Message{
			Type:      "command_result",
			RequestID: msg.RequestID,
			Data: map[string]interface{}{
				"service_id": serviceID,
				"action":     action,
				"success":    false,
				"error":      "Unknown action",
			},
		}
		SendMessage(response)
	}
}

// handleUpdate 处理后端下发的批量更新指令，异步执行并通过 update_progress 上报进度。
func handleUpdate(msg Message) {
	taskID := toString(msg.Data["task_id"])
	updateType := toString(msg.Data["update_type"])
	downloadToken := toString(msg.Data["download_token"])

	if taskID == "" || downloadToken == "" {
		log.Printf("[UPDATE] invalid update message: missing task_id or download_token")
		SendUpdateProgress(taskID, "参数不完整", "failed", 0, "缺少 task_id 或 download_token")
		return
	}

	params := manager.UpdateParams{
		TaskID:     taskID,
		UpdateType: updateType,
		FileURL:    buildDownloadURL(downloadToken),
		FileSHA256: toString(msg.Data["file_sha256"]),
		FileName:   toString(msg.Data["file_name"]),
		Version:    toString(msg.Data["version"]),
		// docker
		ImageName:     toString(msg.Data["image_name"]),
		ImageTag:      toString(msg.Data["image_tag"]),
		ContainerName: toString(msg.Data["container_name"]),
		ComposeFile:   toString(msg.Data["compose_file"]),
		// binary
		BinaryTargetPath:      toString(msg.Data["binary_target_path"]),
		BinaryServiceName:     toString(msg.Data["binary_service_name"]),
		BackupBeforeUpdate:     toBool(msg.Data["backup_before_update"]),
		AutoStopOld:            toBool(msg.Data["auto_stop_old"]),
		AutoStartAfter:         toBool(msg.Data["auto_start_after"]),
		// 可选：同步配置文件
		ComposeFileContent:  toString(msg.Data["compose_file_content"]),
		ConfigFileContent:   toString(msg.Data["config_file_content"]),
		ServiceFileContent:  toString(msg.Data["service_file_content"]),
	}

	log.Printf("[UPDATE] starting update task=%s type=%s", taskID, updateType)

	go manager.ExecuteUpdate(params, func(step string, status string, progress int, errMsg string) {
		SendUpdateProgress(taskID, step, status, progress, errMsg)
	})
}

// SendUpdateProgress 上报批量更新进度。
func SendUpdateProgress(taskID, step, status string, progress int, errMsg string) error {
	msg := Message{
		Type: "update_progress",
		Data: map[string]interface{}{
			"task_id":  taskID,
			"step":     step,
			"status":   status,
			"progress": progress,
			"error":    errMsg,
		},
	}
	if err := SendMessage(msg); err != nil {
		log.Printf("[UPDATE] send update_progress failed: %v", err)
		return err
	}
	return nil
}

// buildDownloadURL 由 server.url 推导后端 HTTP 下载地址（ws->http, wss->https）。
func buildDownloadURL(token string) string {
	u, err := url.Parse(config.GlobalConfig.Server.URL)
	if err != nil || u.Host == "" {
		return "http://localhost:8000/api/agent-update/files/" + token
	}
	scheme := "http"
	if u.Scheme == "wss" {
		scheme = "https"
	}
	return fmt.Sprintf("%s://%s/api/agent-update/files/%s", scheme, u.Host, token)
}

// toBool 宽容转换布尔值（后端 JSON bool 或 1/0）。
func toBool(v interface{}) bool {
	switch b := v.(type) {
	case bool:
		return b
	case float64:
		return b != 0
	case int:
		return b != 0
	case string:
		return b == "true" || b == "1"
	default:
		return false
	}
}

func SendMessage(msg Message) error {
	if conn == nil {
		return fmt.Errorf("not connected")
	}

	msg.Timestamp = float64(time.Now().Unix())
	if msg.RequestID == "" {
		msg.RequestID = fmt.Sprintf("%d", time.Now().UnixNano())
	}

	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}

	return conn.WriteMessage(websocket.TextMessage, data)
}

func SendRegistration() error {
	metrics := collector.CollectSystemMetrics()

	registration := Registration{
		UUID:          config.AgentUUID,
		Hostname:      metrics.Hostname,
		IP:            metrics.IP,
		OS:            metrics.OS,
		Kernel:        metrics.Kernel,
		Arch:          metrics.Arch,
		CPUModel:      metrics.CPUModel,
		CPUCores:      metrics.CPUCores,
		MemoryTotal:   metrics.MemoryTotal,
		AgentVersion:  config.GlobalConfig.Deploy.Version,
		Capabilities:  []string{"system", "process", "docker"},
		Tags:          []string{},
		// 部署元信息
		DeployMethod: config.GlobalConfig.Deploy.Method,
		DeployDir:    config.GlobalConfig.Deploy.DeployDir,
		ComposeFile:  config.GlobalConfig.Deploy.ComposeFile,
		BinaryPath:   config.GlobalConfig.Deploy.BinaryPath,
		ServiceName:  config.GlobalConfig.Deploy.ServiceName,
		UpdatesDir:   config.GlobalConfig.Deploy.UpdatesDir,
		BackupDir:    config.GlobalConfig.Deploy.BackupDir,
	}

	msg := Message{
		Type: "register",
		Data: map[string]interface{}{
			"registration": registration,
		},
	}

	return SendMessage(msg)
}

func SendHeartbeat(metrics collector.SystemMetrics, services []collector.ServiceStatus) error {
	heartbeat := Heartbeat{
		System:          metrics,
		Services:        services,
		DockerContainers: []ContainerStatus{},
		ComposeProjects: []ComposeStatus{},
	}

	msg := Message{
		Type: "heartbeat",
		Data: map[string]interface{}{
			"heartbeat": heartbeat,
		},
	}

	return SendMessage(msg)
}

func reconnect() {
	reconnectCount++
	// 不设放弃上限：Agent 必须长期在线，后端重启/网络抖动后要能自愈。
	// 早期版本在超过 maxReconnectAttempts 时 log.Fatalf 退出进程，
	// 导致后端重启后 Agent 永久离线，只能人工重启。
	if reconnectCount%maxReconnectAttempts == 0 {
		log.Printf("Reconnect attempts reached %d, keep retrying (backoff capped at 30s)", reconnectCount)
	}

	log.Printf("Reconnecting in %v (attempt %d)", reconnectDelay, reconnectCount)
	time.Sleep(reconnectDelay)

	// 退避上限 30s：过长会导致注册失败后要等数分钟才恢复在线
	reconnectDelay = time.Duration(float64(reconnectDelay) * 1.5)
	if reconnectDelay > 30*time.Second {
		reconnectDelay = 30 * time.Second
	}

	if err := Connect(); err != nil {
		log.Printf("Reconnect failed: %v", err)
		// 清空残留的 broken 连接，避免后续逻辑误判为"已连接"
		conn = nil
		// 交给 ReconnectLoop 继续重试，避免递归叠加 reconnectCount
		go ReconnectLoop()
		return
	}

	log.Printf("Reconnected successfully")
	go SendRegistrationWithRetry()
}

func ReconnectLoop() {
	for {
		// 注意：不能用 conn == nil 判断是否需要重连。
		// Connect() 失败时不会清空 conn，残留的旧连接（已 broken）会让
		// 这里误判为"已连接"而直接 return，导致 Agent 永久离线。
		// 因此这里无条件重试，直到 Connect() 成功为止。
		log.Printf("Attempting to connect...")
		if err := Connect(); err != nil {
			log.Printf("Connect failed: %v", err)
			time.Sleep(reconnectDelay)
			reconnectDelay = time.Duration(float64(reconnectDelay) * 1.5)
			if reconnectDelay > 30*time.Second {
				reconnectDelay = 30 * time.Second
			}
			continue
		}
		log.Printf("Connected successfully")
		reconnectDelay = time.Second
		reconnectCount = 0
		time.Sleep(2 * time.Second)
		go SendRegistrationWithRetry()
		return
	}
}

func Close() {
	if conn != nil {
		conn.Close()
	}
}

// HandlePendingUpdate 启动时检查 pending.json：
// 1. 如果存在且 compose 还没 up → 执行 compose up
// 2. 连接建立并注册成功后 → 主动上报 update_progress success → 清 pending
// 避免 compose down 杀掉容器后 up 还没执行（自杀悖论）。
func HandlePendingUpdate() {
	// Step 1: 执行 compose up（如果还没 up）
	pending := manager.CheckPendingUpdate()
	if pending == nil {
		return
	}

	// Step 2: 等连接建立且注册完成后再上报 success
	go func() {
		// 等注册确认（最多 120s）：仅 conn != nil 不够，此时可能尚未注册成功，
		// 上报会因连接未就绪而静默失败，导致任务永远卡在 95%
		for i := 0; i < 240; i++ {
			if conn != nil && isRegisterAcked() {
				break
			}
			time.Sleep(500 * time.Millisecond)
		}

		// 上报 success，失败则重试，成功后才清理 pending
		for i := 1; i <= 10; i++ {
			if err := SendUpdateProgress(pending.TaskID, "接力完成", "success", 100, ""); err == nil {
				log.Printf("[PENDING] reported success for task=%s version=%s", pending.TaskID, pending.Version)
				manager.RemovePendingFile()
				return
			} else {
				log.Printf("[PENDING] report success failed (attempt %d/10): %v", i, err)
			}
			time.Sleep(3 * time.Second)
		}
		log.Printf("[PENDING] gave up reporting success for task=%s, pending kept for next restart", pending.TaskID)
	}()
}