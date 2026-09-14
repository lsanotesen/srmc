# -*- coding: utf-8 -*-
"""
迁移脚本：Agent 批量更新功能
1. 创建 agent_update_tasks 表
2. 创建 agent_update_task_items 表
3. ALTER audit_logs.action 枚举新增 AGENT_UPDATE / AGENT_UPDATE_CANCEL
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine
from sqlalchemy import text

DDL_TASK = """
CREATE TABLE IF NOT EXISTS agent_update_tasks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(36) UNIQUE NOT NULL COMMENT '任务ID(UUID)',
  update_type ENUM('docker','binary') NOT NULL COMMENT '更新类型',
  file_name VARCHAR(255) NOT NULL COMMENT '原始文件名',
  file_path VARCHAR(500) NOT NULL COMMENT '服务端临时文件路径',
  file_size BIGINT DEFAULT 0 COMMENT '文件大小(bytes)',
  file_sha256 VARCHAR(64) NOT NULL COMMENT '文件SHA256',
  version VARCHAR(64) COMMENT '版本号/镜像Tag',
  image_name VARCHAR(255) COMMENT '镜像名称',
  image_tag VARCHAR(100) COMMENT '镜像Tag',
  container_name VARCHAR(128) COMMENT '目标容器名(可选)',
  binary_target_path VARCHAR(500) COMMENT '目标路径',
  binary_service_name VARCHAR(128) COMMENT '服务名称/启动方式',
  backup_before_update TINYINT DEFAULT 1 COMMENT '更新前备份',
  auto_stop_old TINYINT DEFAULT 1 COMMENT '自动停止旧程序',
  auto_start_after TINYINT DEFAULT 1 COMMENT '更新后自动启动',
  total_count INT DEFAULT 0,
  success_count INT DEFAULT 0,
  failed_count INT DEFAULT 0,
  running_count INT DEFAULT 0,
  waiting_count INT DEFAULT 0,
  cancelled_count INT DEFAULT 0,
  status ENUM('waiting','running','success','failed','partial','cancelled') DEFAULT 'waiting',
  created_by VARCHAR(64),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_aut_status(status),
  INDEX idx_aut_created_at(created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent批量更新任务';
"""

DDL_ITEM = """
CREATE TABLE IF NOT EXISTS agent_update_task_items (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(36) NOT NULL,
  agent_uuid VARCHAR(64) NOT NULL,
  hostname VARCHAR(128),
  ip VARCHAR(45),
  status ENUM('waiting','running','success','failed','cancelled','skipped') DEFAULT 'waiting',
  current_step VARCHAR(255) COMMENT '当前步骤',
  progress INT DEFAULT 0 COMMENT '进度 0-100',
  error_message TEXT,
  started_at DATETIME,
  finished_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_auti_task_id(task_id),
  INDEX idx_auti_agent(agent_uuid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent批量更新明细';
"""

AUDIT_ENUM_ALTER = """
ALTER TABLE audit_logs MODIFY COLUMN action ENUM(
  "START","STOP","RESTART","SHELL","LOG","SQL","IMPORT","EXPORT",
  "LOGIN","CREATE","UPDATE","DELETE","PROJECT_CREATE","PROJECT_UPDATE",
  "PROJECT_DELETE","PROJECT_IMPORT","CREATE_PROJECT","DELETE_PROJECT",
  "SERVICE_CREATE","SERVICE_UPDATE","SERVICE_DELETE","SERVICE_START",
  "SERVICE_STOP","SERVICE_RESTART","SERVICE_AUTOSTART","SUBSYSTEM_CREATE",
  "SUBSYSTEM_UPDATE","SUBSYSTEM_DELETE","SERVICE_GROUP_CREATE",
  "SERVICE_GROUP_UPDATE","SERVICE_GROUP_DELETE","SERVICE_GROUP_CLEANUP",
  "SERVICE_IMPORT",
  "AGENT_CONTROL","AGENT_BATCH_CONTROL","ROLE_CREATE","ROLE_UPDATE",
  "ROLE_DELETE","PERMISSION_GRANT","PERMISSION_REVOKE","PROJECT_SHARE",
  "PROJECT_SHARE_REMOVE","ORG_CREATE","ORG_UPDATE","ORG_DELETE",
  "DEPT_CREATE","DEPT_UPDATE","DEPT_DELETE",
  "PROJECT_MEMBER_BATCH_ADD",
  "BACKUP_CREATE","BACKUP_RESTORE","IMPORT_REVERT",
  "AGENT_UPDATE","AGENT_UPDATE_CANCEL"
) NOT NULL
"""


def table_exists(conn, name):
    r = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = :n"), {"n": name})
    return r.scalar() > 0


def main():
    with engine.connect() as conn:
        for ddl, name in [
            (DDL_TASK, "agent_update_tasks"),
            (DDL_ITEM, "agent_update_task_items"),
        ]:
            if not table_exists(conn, name):
                conn.execute(text(ddl))
                print(f"[OK] created table {name}")
            else:
                print(f"[SKIP] {name} exists")

        try:
            conn.execute(text(AUDIT_ENUM_ALTER))
            print("[OK] audit_logs.action enum updated")
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg:
                print("[SKIP] audit_logs.action already contains new values")
            else:
                print(f"[WARN] audit_logs.action alter skipped (may already exist): {e}")
        conn.commit()
    print("Migration 0011 done.")


if __name__ == "__main__":
    main()