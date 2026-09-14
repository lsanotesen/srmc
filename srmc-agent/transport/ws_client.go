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
func SendUpdateProgress(taskID, step, status string, progress int, errMsg string) {
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
	}
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
		Arch:          "",
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
	if reconnectCount > maxReconnectAttempts {
		log.Fatalf("Max reconnect attempts reached")
	}

	log.Printf("Reconnecting in %v (attempt %d/%d)", reconnectDelay, reconnectCount, maxReconnectAttempts)
	time.Sleep(reconnectDelay)

	reconnectDelay = time.Duration(float64(reconnectDelay) * 1.5)
	if reconnectDelay > 5*time.Minute {
		reconnectDelay = 5 * time.Minute
	}

	if err := Connect(); err != nil {
		log.Printf("Reconnect failed: %v", err)
		reconnect()
	}

	log.Printf("Reconnected successfully")
	SendRegistration()
}

func ReconnectLoop() {
	for {
		if conn == nil {
			log.Printf("Attempting to connect...")
			if err := Connect(); err != nil {
				log.Printf("Connect failed: %v", err)
				time.Sleep(reconnectDelay)
				reconnectDelay = time.Duration(float64(reconnectDelay) * 1.5)
				if reconnectDelay > 30*time.Second {
					reconnectDelay = 30 * time.Second
				}
			} else {
				log.Printf("Connected successfully")
				reconnectDelay = time.Second
				reconnectCount = 0
				time.Sleep(2 * time.Second)
				SendRegistration()
				return
			}
		} else {
			return
		}
	}
}

func Close() {
	if conn != nil {
		conn.Close()
	}
}

// HandlePendingUpdate 启动时检查 pending.json：
// 1. 如果存在且 compose 还没 up → 执行 compose up
// 2. 连接建立后 → 主动上报 update_progress success → 清 pending
// 避免 compose down 杀掉容器后 up 还没执行（自杀悖论）。
func HandlePendingUpdate() {
	// Step 1: 执行 compose up（如果还没 up）
	pending := manager.CheckPendingUpdate()
	if pending == nil {
		return
	}

	// Step 2: 等连接建立后主动上报 success
	go func() {
		// 等连接就绪（最多 60s）
		for i := 0; i < 30; i++ {
			time.Sleep(2 * time.Second)
			if conn != nil {
				break
			}
		}

		// 上报 success
		SendUpdateProgress(pending.TaskID, "接力完成", "success", 100, "")
		log.Printf("[PENDING] reported success for task=%s version=%s", pending.TaskID, pending.Version)

		// 清理 pending.json + tar
		manager.RemovePendingFile()
	}()
}