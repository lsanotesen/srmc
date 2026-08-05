-- ============================================================
-- SRMC 企业级权限体系迁移脚本
-- 版本: 2.0.0
-- 日期: 2026-08-03
-- ============================================================

-- 1. 组织机构表
CREATE TABLE IF NOT EXISTS organizations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '组织名称',
    code VARCHAR(50) NOT NULL UNIQUE COMMENT '组织编码',
    logo VARCHAR(500) COMMENT 'Logo URL',
    description TEXT COMMENT '描述',
    status TINYINT(1) NOT NULL DEFAULT 1 COMMENT '状态: 1-启用, 0-禁用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_code (code),
    INDEX idx_org_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组织机构表';

-- 2. 部门表（树形结构）
CREATE TABLE IF NOT EXISTS departments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    organization_id BIGINT NOT NULL COMMENT '所属组织ID',
    parent_id BIGINT DEFAULT NULL COMMENT '父部门ID, NULL表示根部门',
    name VARCHAR(100) NOT NULL COMMENT '部门名称',
    code VARCHAR(50) NOT NULL COMMENT '部门编码',
    leader_id BIGINT COMMENT '部门负责人用户ID',
    description TEXT COMMENT '描述',
    status TINYINT(1) NOT NULL DEFAULT 1 COMMENT '状态: 1-启用, 0-禁用',
    sort_order INT DEFAULT 0 COMMENT '排序',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_dept_org (organization_id),
    INDEX idx_dept_parent (parent_id),
    INDEX idx_dept_code (code),
    INDEX idx_dept_status (status),
    CONSTRAINT fk_dept_org FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='部门表';

-- 3. 扩展用户表
ALTER TABLE users ADD COLUMN organization_id BIGINT COMMENT '所属组织ID';
ALTER TABLE users ADD COLUMN department_id BIGINT COMMENT '所属部门ID';
ALTER TABLE users ADD COLUMN job_title VARCHAR(100) COMMENT '职位';
ALTER TABLE users ADD COLUMN status TINYINT(1) NOT NULL DEFAULT 1 COMMENT '状态: 1-启用, 0-禁用';
ALTER TABLE users ADD INDEX idx_user_org (organization_id);
ALTER TABLE users ADD INDEX idx_user_dept (department_id);

-- 4. 扩展项目表
ALTER TABLE projects ADD COLUMN organization_id BIGINT COMMENT '所属组织ID';
ALTER TABLE projects ADD COLUMN department_id BIGINT COMMENT '所属部门ID';
ALTER TABLE projects ADD COLUMN creator_id BIGINT COMMENT '创建人ID';
ALTER TABLE projects ADD COLUMN owner_id BIGINT COMMENT '负责人ID';
ALTER TABLE projects ADD COLUMN visibility ENUM('DEPARTMENT', 'AUTHORIZED', 'PUBLIC') NOT NULL DEFAULT 'DEPARTMENT' COMMENT '可见性: DEPARTMENT-本部门, AUTHORIZED-授权可见, PUBLIC-组织内公开';
ALTER TABLE projects ADD INDEX idx_project_org (organization_id);
ALTER TABLE projects ADD INDEX idx_project_dept (department_id);
ALTER TABLE projects ADD INDEX idx_project_visibility (visibility);

-- 5. 项目成员表
CREATE TABLE IF NOT EXISTS project_members (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT NOT NULL COMMENT '项目ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    role ENUM('Owner', 'Manager', 'Developer', 'Operator', 'Viewer') NOT NULL DEFAULT 'Viewer' COMMENT '项目角色',
    join_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_project_user (project_id, user_id),
    INDEX idx_pm_project (project_id),
    INDEX idx_pm_user (user_id),
    INDEX idx_pm_role (role),
    CONSTRAINT fk_pm_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_pm_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目成员表';

-- 6. 项目共享授权表
CREATE TABLE IF NOT EXISTS project_permissions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT NOT NULL COMMENT '项目ID',
    target_type ENUM('Organization', 'Department', 'User') NOT NULL COMMENT '授权目标类型',
    target_id BIGINT NOT NULL COMMENT '授权目标ID',
    permission ENUM('READ', 'EDIT', 'MANAGE') NOT NULL DEFAULT 'READ' COMMENT '权限等级',
    created_by BIGINT NOT NULL COMMENT '创建人ID',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_pp_project (project_id),
    INDEX idx_pp_target (target_type, target_id),
    INDEX idx_pp_permission (permission),
    CONSTRAINT fk_pp_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目共享授权表';

-- 7. 资源组表
CREATE TABLE IF NOT EXISTS resource_groups (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id BIGINT NOT NULL COMMENT '项目ID',
    name VARCHAR(100) NOT NULL COMMENT '资源组名称',
    description TEXT COMMENT '描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_rg_project (project_id),
    CONSTRAINT fk_rg_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资源组表';

-- 8. 角色表（支持自定义角色）
CREATE TABLE IF NOT EXISTS roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL COMMENT '角色名称',
    description VARCHAR(255) COMMENT '角色描述',
    is_system TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否系统内置角色（不可删除）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_role_name (name),
    INDEX idx_role_system (is_system)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色表';

-- 9. 权限定义表
CREATE TABLE IF NOT EXISTS permissions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    resource VARCHAR(50) NOT NULL COMMENT '资源类型: project, service, docker, image, webshell, host, config, log, script, file',
    action VARCHAR(50) NOT NULL COMMENT '操作: view, add, edit, delete, start, stop, restart, exec, remove, upload, download, login, run, reboot, share',
    name VARCHAR(100) NOT NULL COMMENT '权限名称',
    description VARCHAR(255) COMMENT '权限描述',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_resource_action (resource, action),
    INDEX idx_perm_resource (resource)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='权限定义表';

-- 10. 角色-权限关联表
CREATE TABLE IF NOT EXISTS role_permissions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    role_id BIGINT NOT NULL COMMENT '角色ID',
    permission_id BIGINT NOT NULL COMMENT '权限ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_role_perm (role_id, permission_id),
    INDEX idx_rp_role (role_id),
    INDEX idx_rp_perm (permission_id),
    CONSTRAINT fk_rp_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    CONSTRAINT fk_rp_perm FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色-权限关联表';

-- 11. 用户-角色关联表
CREATE TABLE IF NOT EXISTS user_roles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    role_id BIGINT NOT NULL COMMENT '角色ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_role (user_id, role_id),
    INDEX idx_ur_user (user_id),
    INDEX idx_ur_role (role_id),
    CONSTRAINT fk_ur_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_ur_role FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户-角色关联表';

-- 12. 扩展审计日志表
ALTER TABLE audit_logs ADD COLUMN organization_id BIGINT COMMENT '组织ID';
ALTER TABLE audit_logs ADD COLUMN department_id BIGINT COMMENT '部门ID';
ALTER TABLE audit_logs ADD COLUMN request_url VARCHAR(500) COMMENT '请求URL';
ALTER TABLE audit_logs ADD COLUMN request_params TEXT COMMENT '请求参数';
ALTER TABLE audit_logs ADD COLUMN user_agent VARCHAR(500) COMMENT '浏览器UA';
ALTER TABLE audit_logs ADD INDEX idx_audit_org (organization_id);
ALTER TABLE audit_logs ADD INDEX idx_audit_dept (department_id);

-- ============================================================
-- 回滚脚本
-- ============================================================
-- DROP TABLE IF EXISTS role_permissions;
-- DROP TABLE IF EXISTS user_roles;
-- DROP TABLE IF EXISTS permissions;
-- DROP TABLE IF EXISTS roles;
-- DROP TABLE IF EXISTS project_permissions;
-- DROP TABLE IF EXISTS project_members;
-- DROP TABLE IF EXISTS resource_groups;
-- DROP TABLE IF EXISTS departments;
-- DROP TABLE IF EXISTS organizations;
-- 
-- ALTER TABLE audit_logs DROP COLUMN organization_id;
-- ALTER TABLE audit_logs DROP COLUMN department_id;
-- ALTER TABLE audit_logs DROP COLUMN request_url;
-- ALTER TABLE audit_logs DROP COLUMN request_params;
-- ALTER TABLE audit_logs DROP COLUMN user_agent;
-- 
-- ALTER TABLE projects DROP COLUMN organization_id;
-- ALTER TABLE projects DROP COLUMN department_id;
-- ALTER TABLE projects DROP COLUMN creator_id;
-- ALTER TABLE projects DROP COLUMN owner_id;
-- ALTER TABLE projects DROP COLUMN visibility;
-- 
-- ALTER TABLE users DROP COLUMN organization_id;
-- ALTER TABLE users DROP COLUMN department_id;
-- ALTER TABLE users DROP COLUMN job_title;
-- ALTER TABLE users DROP COLUMN status;