# -*- coding: utf-8 -*-
"""
迁移脚本：数据库备份与导入批次功能
1. 创建 db_backup_configs / db_backup_records 表
2. 创建 import_batches / import_batch_operations 表
3. ALTER audit_logs.action 枚举新增备份/撤销相关值
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine
from sqlalchemy import text

DDL_BACKUP_CONFIG = """
CREATE TABLE IF NOT EXISTS db_backup_configs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  enabled TINYINT(1) DEFAULT 0 COMMENT '定时备份开关',
  schedule_type ENUM('daily','weekly') DEFAULT 'daily' COMMENT '调度类型',
  schedule_time TIME DEFAULT '02:00' COMMENT '执行时间',
  week_day TINYINT DEFAULT 1 COMMENT 'weekly时生效 0=周一..6=周日',
  retention_count INT DEFAULT 10 COMMENT '保留份数,自动清理旧备份',
  last_run_at DATETIME NULL COMMENT '上次执行时间',
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据库备份配置';
"""

DDL_BACKUP_RECORD = """
CREATE TABLE IF NOT EXISTS db_backup_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  filename VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  file_size BIGINT DEFAULT 0,
  backup_type ENUM('manual','scheduled','pre_import','pre_restore') DEFAULT 'manual',
  status ENUM('running','success','failed') DEFAULT 'running',
  table_count INT DEFAULT 0,
  row_count BIGINT DEFAULT 0,
  duration_ms INT DEFAULT 0,
  error_message TEXT NULL,
  created_by VARCHAR(64),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_bk_created_at(created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

DDL_IMPORT_BATCH = """
CREATE TABLE IF NOT EXISTS import_batches (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_no VARCHAR(36) UNIQUE NOT NULL,
  filename VARCHAR(255),
  project_id BIGINT NOT NULL,
  project_name VARCHAR(100),
  subsystem_id INT NULL,
  group_id INT NULL,
  added_count INT DEFAULT 0,
  repaired_count INT DEFAULT 0,
  skipped_count INT DEFAULT 0,
  failed_count INT DEFAULT 0,
  auto_created_group_ids TEXT COMMENT 'JSON数组,本次导入新建的分类ID',
  default_subsystem_created TINYINT(1) DEFAULT 0,
  pre_backup_record_id BIGINT NULL COMMENT '导入前快照记录ID',
  status ENUM('active','reverted') DEFAULT 'active',
  reverted_at DATETIME NULL,
  reverted_by VARCHAR(64) NULL,
  created_by VARCHAR(64),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_ib_status(status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

DDL_IMPORT_BATCH_OP = """
CREATE TABLE IF NOT EXISTS import_batch_operations (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_id BIGINT NOT NULL,
  op_type ENUM('created','repaired') NOT NULL,
  service_id BIGINT NOT NULL,
  old_project_id BIGINT NULL,
  old_subsystem_id INT NULL,
  old_group_id INT NULL,
  INDEX idx_op_batch(batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# audit_logs.action 枚举追加
AUDIT_ENUM_ADD = ("BACKUP_CREATE", "BACKUP_RESTORE", "IMPORT_REVERT")

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
  "BACKUP_CREATE","BACKUP_RESTORE","IMPORT_REVERT"
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
            (DDL_BACKUP_CONFIG, "db_backup_configs"),
            (DDL_BACKUP_RECORD, "db_backup_records"),
            (DDL_IMPORT_BATCH, "import_batches"),
            (DDL_IMPORT_BATCH_OP, "import_batch_operations"),
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
            if "truncated" in msg or "incorrect" in msg:
                print(f"[WARN] audit_logs.action alter skipped/failed: {e}")
            elif "duplicate" in msg:
                print("[SKIP] audit_logs.action already contains new values")
            else:
                raise
        conn.commit()
    print("Migration done.")


if __name__ == "__main__":
    main()
