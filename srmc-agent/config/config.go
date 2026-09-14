package config

import (
	"github.com/google/uuid"
	"github.com/spf13/viper"
	"log"
	"os"
	"path/filepath"
	"strings"
)

type Config struct {
	Server    ServerConfig    `mapstructure:"server"`
	Agent     AgentConfig     `mapstructure:"agent"`
	Collector CollectorConfig `mapstructure:"collector"`
	Manager   ManagerConfig   `mapstructure:"manager"`
	Docker    DockerConfig    `mapstructure:"docker"`
	Systemd   SystemdConfig   `mapstructure:"systemd"`
	Deploy    DeployConfig    `mapstructure:"deploy"`
}

type AgentConfig struct {
	UUID string `mapstructure:"uuid"`
	Name string `mapstructure:"name"`
	IP   string `mapstructure:"ip"`
}

// DeployConfig Agent 自身部署元信息（与规范对齐）：
// - Method:      auto / docker / binary，auto 由启动时探测
// - DeployDir:   Agent 根部署目录，默认 /etc/srmc-agent
// - UpdatesDir:  更新工作目录，默认 DeployDir/updates（放 pending.json、下载的 tar）
// - BackupDir:   备份目录，默认 DeployDir/backup
// - BackupKeep:  保留的旧备份/旧镜像份数，默认 2
// - BinaryPath:  二进制文件路径（留空自动补）
// - ComposeFile: docker-compose.yml 路径（留空自动补）
// - ServiceName: systemd 服务名，默认 srmc-agent
// - Version:     Agent 自身版本号（后端靠它判更新成功）
type DeployConfig struct {
	Method      string `mapstructure:"method"`
	DeployDir   string `mapstructure:"deploy_dir"`
	UpdatesDir  string `mapstructure:"updates_dir"`
	BackupDir   string `mapstructure:"backup_dir"`
	BackupKeep  int    `mapstructure:"backup_keep"`
	BinaryPath  string `mapstructure:"binary_path"`
	ComposeFile string `mapstructure:"compose_file"`
	ServiceName string `mapstructure:"service_name"`
	Version     string `mapstructure:"version"`
}

// === 向后兼容：旧配置用 deploy_type 也能跑 ===

// DeployType 是旧字段（deploy_type），viper mapstructure 只认 DeployConfig 里的 tag。
// 旧 config.yaml 里写了 deploy_type 会被忽略，但 normalizeDeployConfig 会用 Method 兜底。
// 为了平滑过渡，在 Init 里手动把旧 deploy_type 映射到 Method。

type ServerConfig struct {
	URL   string `mapstructure:"url"`
	Token string `mapstructure:"token"`
}

type CollectorConfig struct {
	Interval          int `mapstructure:"interval"`
	HeartbeatInterval int `mapstructure:"heartbeat_interval"`
}

type ManagerConfig struct {
	Timeout int `mapstructure:"timeout"`
}

type DockerConfig struct {
	Socket string `mapstructure:"socket"`
}

type SystemdConfig struct {
	UseDbus bool `mapstructure:"use_dbus"`
}

var GlobalConfig Config
var AgentUUID string
var configDir string

func Init(configPath string) {
	viper.SetConfigType("yaml")
	viper.SetConfigFile(configPath)

	viper.SetDefault("server.url", "ws://localhost:8000/ws/agent/")
	viper.SetDefault("server.token", "")
	viper.SetDefault("collector.interval", 2)
	viper.SetDefault("collector.heartbeat_interval", 5)
	viper.SetDefault("manager.timeout", 30)
	viper.SetDefault("docker.socket", "unix:///var/run/docker.sock")
	viper.SetDefault("systemd.use_dbus", true)
	viper.SetDefault("deploy.method", "auto")
	viper.SetDefault("deploy.deploy_dir", "/etc/srmc-agent")
	viper.SetDefault("deploy.updates_dir", "")
	viper.SetDefault("deploy.backup_dir", "")
	viper.SetDefault("deploy.backup_keep", 2)
	viper.SetDefault("deploy.binary_path", "")
	viper.SetDefault("deploy.compose_file", "")
	viper.SetDefault("deploy.service_name", "srmc-agent")
	viper.SetDefault("deploy.version", "")

	err := viper.ReadInConfig()
	if err != nil {
		log.Printf("Warning: config file not found, using defaults: %v", err)
	}

	// 向后兼容：旧字段 deploy_type 映射到 method
	if viper.IsSet("deploy.deploy_type") && !viper.IsSet("deploy.method") {
		oldType := viper.GetString("deploy.deploy_type")
		if oldType != "" {
			viper.Set("deploy.method", oldType)
		}
	}

	err = viper.Unmarshal(&GlobalConfig)
	if err != nil {
		log.Fatalf("Unable to unmarshal config: %v", err)
	}

	// 部署元信息补全与探测
	normalizeDeployConfig()

	// 获取配置文件目录，用于保存 UUID 文件
	configDir = filepath.Dir(configPath)
	uuidFile := filepath.Join(configDir, ".agent_uuid")

	// 优先级：配置文件 > 本地文件 > 自动生成
	if GlobalConfig.Agent.UUID != "" {
		AgentUUID = GlobalConfig.Agent.UUID
		log.Printf("Agent UUID from config: %s", AgentUUID)
	} else if savedUUID, err := os.ReadFile(uuidFile); err == nil && len(savedUUID) > 0 {
		AgentUUID = string(savedUUID)
		log.Printf("Agent UUID from file: %s", AgentUUID)
	} else {
		AgentUUID = generateUUID()
		if err := os.WriteFile(uuidFile, []byte(AgentUUID), 0600); err != nil {
			log.Printf("Warning: cannot save UUID to %s: %v", uuidFile, err)
		} else {
			log.Printf("Agent UUID generated and saved to %s: %s", uuidFile, AgentUUID)
		}
	}

	log.Printf("Agent UUID: %s", AgentUUID)
}

func generateUUID() string {
	return uuid.New().String()
}

// normalizeDeployConfig 补全 deploy 配置：探测部署类型，填充路径默认值，自动建目录。
// 探测优先级：method 显式指定 > 进程在容器内则 docker > 默认 binary。
func normalizeDeployConfig() {
	d := &GlobalConfig.Deploy

	// 补 deploy_dir
	if d.DeployDir == "" {
		d.DeployDir = "/etc/srmc-agent"
	}
	// 补 method（默认 auto → 探测）
	if d.Method == "" || d.Method == "auto" {
		if isRunningInContainer() {
			d.Method = "docker"
		} else {
			d.Method = "binary"
		}
	}
	// 补 updates_dir / backup_dir
	if d.UpdatesDir == "" {
		d.UpdatesDir = filepath.Join(d.DeployDir, "updates")
	}
	if d.BackupDir == "" {
		d.BackupDir = filepath.Join(d.DeployDir, "backup")
	}
	// 补 backup_keep
	if d.BackupKeep < 0 {
		d.BackupKeep = 2
	}
	// 补 service_name
	if d.ServiceName == "" {
		d.ServiceName = "srmc-agent"
	}
	// 补 compose_file / binary_path
	if d.ComposeFile == "" {
		d.ComposeFile = filepath.Join(d.DeployDir, "docker-compose.yml")
	}
	if d.BinaryPath == "" {
		d.BinaryPath = filepath.Join(d.DeployDir, "srmc-agent")
	}
	// 补 version（注册时上报，后端靠它判更新成功）
	if d.Version == "" {
		d.Version = "1.0.0"
	}

	// 自动建目录
	for _, dir := range []string{d.DeployDir, d.UpdatesDir, d.BackupDir} {
		if err := os.MkdirAll(dir, 0755); err != nil {
			log.Printf("Warning: cannot create dir %s: %v", dir, err)
		}
	}

	log.Printf("Deploy config: method=%s dir=%s updates=%s backup=%s compose=%s binary=%s service=%s backup_keep=%d version=%s",
		d.Method, d.DeployDir, d.UpdatesDir, d.BackupDir, d.ComposeFile, d.BinaryPath, d.ServiceName, d.BackupKeep, d.Version)
}

// isRunningInContainer 判断 Agent 是否运行在容器内（通过 /.dockerenv 或 cgroup）。
func isRunningInContainer() bool {
	if _, err := os.Stat("/.dockerenv"); err == nil {
		return true
	}
	if data, err := os.ReadFile("/proc/1/cgroup"); err == nil {
		s := string(data)
		if strings.Contains(s, "docker") || strings.Contains(s, "kubepods") || strings.Contains(s, "containerd") {
			return true
		}
	}
	return false
}
