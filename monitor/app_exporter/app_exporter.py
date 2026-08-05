#!/usr/bin/env python3
"""SRMC应用程序监控Exporter"""
from prometheus_client import start_http_server, Gauge, Counter
import psutil
import time
import os
import docker
from typing import Dict, List

# 定义指标
app_status = Gauge('srmc_app_status', 'Application status (1=running, 0=stopped)', ['app_name', 'ip', 'port'])
app_memory_mb = Gauge('srmc_app_memory_mb', 'Application memory usage (MB)', ['app_name', 'ip', 'port'])
app_cpu_percent = Gauge('srmc_app_cpu_percent', 'Application CPU usage percent', ['app_name', 'ip', 'port'])
app_uptime_seconds = Gauge('srmc_app_uptime_seconds', 'Application uptime in seconds', ['app_name', 'ip', 'port'])
docker_container_status = Gauge('srmc_docker_container_status', 'Docker container status (1=running, 0=stopped)', ['container_name', 'ip'])
docker_container_memory_mb = Gauge('srmc_docker_container_memory_mb', 'Docker container memory usage (MB)', ['container_name', 'ip'])
docker_container_cpu_percent = Gauge('srmc_docker_container_cpu_percent', 'Docker container CPU usage percent', ['container_name', 'ip'])

# 从环境变量读取配置
MONITOR_APPS = os.getenv('MONITOR_APPS', '').split(',')
MONITOR_DOCKER_CONTAINERS = os.getenv('MONITOR_DOCKER_CONTAINERS', '').split(',')
LOCAL_IP = os.getenv('LOCAL_IP', 'localhost')

def check_app_status(app_name: str, port: int) -> Dict:
    """检查应用程序状态"""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                process = psutil.Process(conn.pid)
                return {
                    'status': 1,
                    'memory_mb': process.memory_info().rss / 1024 / 1024,
                    'cpu_percent': process.cpu_percent(),
                    'uptime_seconds': time.time() - process.create_time()
                }
    except:
        pass
    
    return {
        'status': 0,
        'memory_mb': 0,
        'cpu_percent': 0,
        'uptime_seconds': 0
    }

def check_docker_container(container_name: str) -> Dict:
    """检查Docker容器状态"""
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        stats = container.stats(stream=False)
        
        # 计算CPU使用率
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        cpu_percent = (cpu_delta / system_delta) * 100 if system_delta > 0 else 0
        
        # 计算内存使用
        memory_usage = stats['memory_stats'].get('usage', 0) / 1024 / 1024
        
        return {
            'status': 1 if container.status == 'running' else 0,
            'memory_mb': memory_usage,
            'cpu_percent': cpu_percent
        }
    except:
        return {
            'status': 0,
            'memory_mb': 0,
            'cpu_percent': 0
        }

def update_metrics():
    """更新所有指标"""
    # 更新应用程序指标
    for app_config in MONITOR_APPS:
        if not app_config:
            continue
        
        try:
            # 解析配置: app_name:port
            app_name, port = app_config.split(':')
            port = int(port)
            
            status_info = check_app_status(app_name, port)
            
            app_status.labels(app_name=app_name, ip=LOCAL_IP, port=port).set(status_info['status'])
            app_memory_mb.labels(app_name=app_name, ip=LOCAL_IP, port=port).set(status_info['memory_mb'])
            app_cpu_percent.labels(app_name=app_name, ip=LOCAL_IP, port=port).set(status_info['cpu_percent'])
            app_uptime_seconds.labels(app_name=app_name, ip=LOCAL_IP, port=port).set(status_info['uptime_seconds'])
        except Exception as e:
            print(f"Error checking app {app_config}: {e}")
    
    # 更新Docker容器指标
    for container_name in MONITOR_DOCKER_CONTAINERS:
        if not container_name:
            continue
        
        try:
            status_info = check_docker_container(container_name)
            
            docker_container_status.labels(container_name=container_name, ip=LOCAL_IP).set(status_info['status'])
            docker_container_memory_mb.labels(container_name=container_name, ip=LOCAL_IP).set(status_info['memory_mb'])
            docker_container_cpu_percent.labels(container_name=container_name, ip=LOCAL_IP).set(status_info['cpu_percent'])
        except Exception as e:
            print(f"Error checking container {container_name}: {e}")

if __name__ == '__main__':
    print(f"Starting SRMC App Exporter on port 9101")
    print(f"Local IP: {LOCAL_IP}")
    print(f"Monitoring apps: {MONITOR_APPS}")
    print(f"Monitoring containers: {MONITOR_DOCKER_CONTAINERS}")
    
    # 启动HTTP服务
    start_http_server(9101)
    
    # 定期更新指标
    while True:
        update_metrics()
        time.sleep(15)