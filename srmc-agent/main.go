package main

import (
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"srmc-agent/config"
	"srmc-agent/collector"
	"srmc-agent/manager"
	"srmc-agent/transport"
)

var configPath = flag.String("config", "/etc/srmc-agent/config.yaml", "Path to config file")

func main() {
	flag.Parse()

	log.SetFlags(log.LstdFlags | log.Lshortfile)
	log.Println("Starting SRMC Agent v1.0.0")

	config.Init(*configPath)
	collector.Init()
	manager.Init()

	log.Printf("Connecting to server: %s", config.GlobalConfig.Server.URL)
	err := transport.Connect()
	if err != nil {
		log.Printf("Initial connect failed, will retry: %v", err)
		go transport.ReconnectLoop()
	} else {
		time.Sleep(2 * time.Second)
		transport.SendRegistration()
	}

	go heartbeatLoop()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	<-sigChan

	log.Println("Shutting down...")
	transport.Close()
}

func heartbeatLoop() {
	ticker := time.NewTicker(time.Duration(config.GlobalConfig.Collector.HeartbeatInterval) * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		metrics := collector.CollectSystemMetrics()
		services := collector.CollectServiceStatus()

		log.Printf("Heartbeat: CPU=%.1f%%, Memory=%.1f%%, Services=%d",
			metrics.CPUPercent, metrics.MemoryPercent, len(services))

		err := transport.SendHeartbeat(metrics, services)
		if err != nil {
			log.Printf("Failed to send heartbeat: %v", err)
		}
	}
}