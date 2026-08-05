"""
数据库迁移执行脚本
创建新表和修改现有表结构（幂等执行）
"""
import sys
sys.path.insert(0, "/app")

from core.database import engine
from sqlalchemy import text


def column_exists(conn, table, column):
    result = conn.execute(text(f"SHOW COLUMNS FROM {table} LIKE '{column}'"))
    return result.fetchone() is not None


def index_exists(conn, table, index):
    result = conn.execute(text(f"SHOW INDEX FROM {table} WHERE Key_name = '{index}'"))
    return result.fetchone() is not None


def run_migration():
    with engine.connect() as conn:
        print("开始执行数据库迁移...")

        # 1. 创建新表
        tables = {
            "organizations": """
                CREATE TABLE IF NOT EXISTS organizations (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    code VARCHAR(50) NOT NULL UNIQUE,
                    logo VARCHAR(500),
                    description TEXT,
                    status TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_org_code (code),
                    INDEX idx_org_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            "departments": """
                CREATE TABLE IF NOT EXISTS departments (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    organization_id BIGINT NOT NULL,
                    parent_id BIGINT DEFAULT NULL,
                    name VARCHAR(100) NOT NULL,
                    code VARCHAR(50) NOT NULL,
                    leader_id BIGINT,
                    description TEXT,
                    status TINYINT(1) NOT NULL DEFAULT 1,
                    sort_order INT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_dept_org (organization_id),
                    INDEX idx_dept_parent (parent_id),
                    INDEX idx_dept_code (code),
                    INDEX idx_dept_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            "project_members": """
                CREATE TABLE IF NOT EXISTS project_members (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    project_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    role ENUM('Owner', 'Manager', 'Developer', 'Operator', 'Viewer') NOT NULL DEFAULT 'Viewer',
                    join_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_project_user (project_id, user_id),
                    INDEX idx_pm_project (project_id),
                    INDEX idx_pm_user (user_id),
                    INDEX idx_pm_role (role)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            "project_permissions": """
                CREATE TABLE IF NOT EXISTS project_permissions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    project_id BIGINT NOT NULL,
                    target_type ENUM('Organization', 'Department', 'User') NOT NULL,
                    target_id BIGINT NOT NULL,
                    permission ENUM('READ', 'EDIT', 'MANAGE') NOT NULL DEFAULT 'READ',
                    created_by BIGINT NOT NULL,
                    created_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_pp_project (project_id),
                    INDEX idx_pp_target (target_type, target_id),
                    INDEX idx_pp_permission (permission)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            "resource_groups": """
                CREATE TABLE IF NOT EXISTS resource_groups (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    project_id BIGINT NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_rg_project (project_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            "roles": """
                CREATE TABLE IF NOT EXISTS roles (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(50) NOT NULL UNIQUE,
                    description VARCHAR(255),
                    is_system TINYINT(1) NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_role_system (is_system)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            "permissions": """
                CREATE TABLE IF NOT EXISTS permissions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    resource VARCHAR(50) NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description VARCHAR(255),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_resource_action (resource, action),
                    INDEX idx_perm_resource (resource)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            "role_permissions": """
                CREATE TABLE IF NOT EXISTS role_permissions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    role_id BIGINT NOT NULL,
                    permission_id BIGINT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_role_perm (role_id, permission_id),
                    INDEX idx_rp_role (role_id),
                    INDEX idx_rp_perm (permission_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
            "user_roles": """
                CREATE TABLE IF NOT EXISTS user_roles (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    role_id BIGINT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_user_role (user_id, role_id),
                    INDEX idx_ur_user (user_id),
                    INDEX idx_ur_role (role_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """,
        }

        for table_name, sql in tables.items():
            print(f"  创建 {table_name} 表...", end=" ")
            conn.execute(text(sql))
            print("✓")

        # 2. 修改 users 表
        user_cols = [
            ("organization_id", "ALTER TABLE users ADD COLUMN organization_id BIGINT COMMENT '所属组织ID'"),
            ("department_id", "ALTER TABLE users ADD COLUMN department_id BIGINT COMMENT '所属部门ID'"),
            ("job_title", "ALTER TABLE users ADD COLUMN job_title VARCHAR(100) COMMENT '职位'"),
            ("status", "ALTER TABLE users ADD COLUMN status TINYINT(1) NOT NULL DEFAULT 1 COMMENT '状态'"),
        ]
        for col_name, sql in user_cols:
            if not column_exists(conn, "users", col_name):
                conn.execute(text(sql))
                print(f"  users 表添加 {col_name} 列 ✓")

        user_indexes = [
            ("idx_user_org", "ALTER TABLE users ADD INDEX idx_user_org (organization_id)"),
            ("idx_user_dept", "ALTER TABLE users ADD INDEX idx_user_dept (department_id)"),
        ]
        for idx_name, sql in user_indexes:
            if not index_exists(conn, "users", idx_name):
                conn.execute(text(sql))
                print(f"  users 表添加 {idx_name} 索引 ✓")

        # 3. 修改 projects 表
        proj_cols = [
            ("organization_id", "ALTER TABLE projects ADD COLUMN organization_id BIGINT COMMENT '所属组织ID'"),
            ("department_id", "ALTER TABLE projects ADD COLUMN department_id BIGINT COMMENT '所属部门ID'"),
            ("creator_id", "ALTER TABLE projects ADD COLUMN creator_id BIGINT COMMENT '创建人ID'"),
            ("owner_id", "ALTER TABLE projects ADD COLUMN owner_id BIGINT COMMENT '负责人ID'"),
            ("visibility", "ALTER TABLE projects ADD COLUMN visibility VARCHAR(20) NOT NULL DEFAULT 'DEPARTMENT' COMMENT '可见性'"),
        ]
        for col_name, sql in proj_cols:
            if not column_exists(conn, "projects", col_name):
                conn.execute(text(sql))
                print(f"  projects 表添加 {col_name} 列 ✓")

        proj_indexes = [
            ("idx_project_org", "ALTER TABLE projects ADD INDEX idx_project_org (organization_id)"),
            ("idx_project_dept", "ALTER TABLE projects ADD INDEX idx_project_dept (department_id)"),
            ("idx_project_visibility", "ALTER TABLE projects ADD INDEX idx_project_visibility (visibility)"),
        ]
        for idx_name, sql in proj_indexes:
            if not index_exists(conn, "projects", idx_name):
                conn.execute(text(sql))
                print(f"  projects 表添加 {idx_name} 索引 ✓")

        # 4. 修改 audit_logs 表
        audit_cols = [
            ("organization_id", "ALTER TABLE audit_logs ADD COLUMN organization_id BIGINT COMMENT '组织ID'"),
            ("department_id", "ALTER TABLE audit_logs ADD COLUMN department_id BIGINT COMMENT '部门ID'"),
            ("request_url", "ALTER TABLE audit_logs ADD COLUMN request_url VARCHAR(500) COMMENT '请求URL'"),
            ("request_params", "ALTER TABLE audit_logs ADD COLUMN request_params TEXT COMMENT '请求参数'"),
            ("user_agent", "ALTER TABLE audit_logs ADD COLUMN user_agent VARCHAR(500) COMMENT '浏览器UA'"),
        ]
        for col_name, sql in audit_cols:
            if not column_exists(conn, "audit_logs", col_name):
                conn.execute(text(sql))
                print(f"  audit_logs 表添加 {col_name} 列 ✓")

        audit_indexes = [
            ("idx_audit_org", "ALTER TABLE audit_logs ADD INDEX idx_audit_org (organization_id)"),
            ("idx_audit_dept", "ALTER TABLE audit_logs ADD INDEX idx_audit_dept (department_id)"),
        ]
        for idx_name, sql in audit_indexes:
            if not index_exists(conn, "audit_logs", idx_name):
                conn.execute(text(sql))
                print(f"  audit_logs 表添加 {idx_name} 索引 ✓")

        # 5. 更新 audit_logs.action 枚举
        new_actions = [
            "ROLE_CREATE", "ROLE_UPDATE", "ROLE_DELETE",
            "PERMISSION_GRANT", "PERMISSION_REVOKE",
            "PROJECT_SHARE", "PROJECT_SHARE_REMOVE",
            "ORG_CREATE", "ORG_UPDATE", "ORG_DELETE",
            "DEPT_CREATE", "DEPT_UPDATE", "DEPT_DELETE",
            "PROJECT_MEMBER_BATCH_ADD",
        ]
        for action in new_actions:
            try:
                conn.execute(text(f"ALTER TABLE audit_logs MODIFY COLUMN action ENUM('START','STOP','RESTART','SHELL','LOG','SQL','IMPORT','EXPORT','LOGIN','CREATE','UPDATE','DELETE','PROJECT_CREATE','PROJECT_UPDATE','PROJECT_DELETE','PROJECT_IMPORT','CREATE_PROJECT','DELETE_PROJECT','SERVICE_CREATE','SERVICE_UPDATE','SERVICE_DELETE','SERVICE_START','SERVICE_STOP','SERVICE_RESTART','SERVICE_AUTOSTART','SUBSYSTEM_CREATE','SUBSYSTEM_UPDATE','SUBSYSTEM_DELETE','SERVICE_GROUP_CREATE','SERVICE_GROUP_UPDATE','SERVICE_GROUP_DELETE','SERVICE_IMPORT','AGENT_CONTROL','AGENT_BATCH_CONTROL','ROLE_CREATE','ROLE_UPDATE','ROLE_DELETE','PERMISSION_GRANT','PERMISSION_REVOKE','PROJECT_SHARE','PROJECT_SHARE_REMOVE','ORG_CREATE','ORG_UPDATE','ORG_DELETE','DEPT_CREATE','DEPT_UPDATE','DEPT_DELETE','PROJECT_MEMBER_BATCH_ADD','{action}')"))
                print(f"  audit_logs.action 枚举添加 {action} ✓")
            except Exception as e:
                if "Duplicate" not in str(e):
                    print(f"  audit_logs.action 枚举添加 {action} 跳过（已存在）")
                else:
                    raise

        conn.commit()
        print("\n数据库迁移完成！")


if __name__ == "__main__":
    run_migration()
