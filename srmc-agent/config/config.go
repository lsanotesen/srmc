package config

import (
	"github.com/google/uuid"
	"github.com/spf13/viper"
	"log"
	"os"
	"path/filepath"
)

type Config struct {
	Server   ServerConfig   `mapstructure:"server"`
	Agent    AgentConfig    `mapstructure:"agent"`
	Collector CollectorConfig `mapstructure:"collector"`
	Manager  ManagerConfig  `mapstructure:"manager"`
	Docker   DockerConfig   `mapstructure:"docker"`
	Systemd  SystemdConfig  `mapstructure:"systemd"`
}

type AgentConfig struct {
	UUID string `mapstructure:"uuid"`
	Name string `mapstructure:"name"`
	IP   string `mapstructure:"ip"`
}

type ServerConfig struct {
	URL   string `mapstructure:"url"`
	Token string `mapstructure:"token"`
}

type CollectorConfig struct {
	Interval         int `mapstructure:"interval"`
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

	err := viper.ReadInConfig()
	if err != nil {
		log.Printf("Warning: config file not found, using defaults: %v", err)
	}

	err = viper.Unmarshal(&GlobalConfig)
	if err != nil {
		log.Fatalf("Unable to unmarshal config: %v", err)
	}

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
		// 保存到本地文件，下次启动时读取
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