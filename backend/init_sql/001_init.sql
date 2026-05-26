CREATE TABLE IF NOT EXISTS `servers` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `hostname` VARCHAR(128) NOT NULL,
    `ip` VARCHAR(45) NOT NULL UNIQUE,
    `ssh_port` INT DEFAULT 22,
    `username` VARCHAR(64) NOT NULL,
    `password` TEXT,
    `private_key` TEXT,
    `os_type` ENUM('LINUX', 'UNIX') DEFAULT 'LINUX',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_servers_ip` (`ip`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `services` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `service_name` VARCHAR(128) NOT NULL,
    `service_code` VARCHAR(64) NOT NULL UNIQUE,
    `service_type` ENUM('APP', 'NGINX', 'REDIS', 'MYSQL', 'KINGBASE', 'DAMENG', 'ELASTICSEARCH', 'RABBITMQ', 'OTHER') NOT NULL,
    `module` VARCHAR(64),
    `environment` ENUM('DEV', 'TEST', 'STAGING', 'PROD') NOT NULL,
    `server_id` BIGINT,
    `ip` VARCHAR(45) NOT NULL,
    `port` INT,
    `service_path` VARCHAR(512),
    `work_dir` VARCHAR(512),
    `start_script` VARCHAR(512),
    `stop_script` VARCHAR(512),
    `restart_script` VARCHAR(512),
    `log_path` VARCHAR(512),
    `check_type` ENUM('PROCESS', 'PORT', 'PID', 'SCRIPT', 'HTTP', 'TCP'),
    `check_keyword` VARCHAR(256),
    `pid_file` VARCHAR(512),
    `owner` VARCHAR(64),
    `remark` TEXT,
    `extra_config` TEXT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_services_service_code` (`service_code`),
    INDEX `idx_services_server_id` (`server_id`),
    INDEX `idx_services_service_type` (`service_type`),
    INDEX `idx_services_environment` (`environment`),
    CONSTRAINT `fk_services_server_id` FOREIGN KEY (`server_id`) REFERENCES `servers`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `users` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(64) NOT NULL UNIQUE,
    `password` VARCHAR(256) NOT NULL,
    `role` ENUM('ADMIN', 'OPS', 'DEV', 'READONLY') NOT NULL DEFAULT 'READONLY',
    `email` VARCHAR(128),
    `phone` VARCHAR(20),
    `is_active` TINYINT(1) DEFAULT 1,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `audit_logs` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT,
    `username` VARCHAR(64) NOT NULL,
    `action` ENUM('START', 'STOP', 'RESTART', 'SHELL', 'LOG', 'SQL', 'IMPORT', 'EXPORT', 'LOGIN', 'CREATE', 'UPDATE', 'DELETE') NOT NULL,
    `service_id` BIGINT,
    `service_code` VARCHAR(64),
    `server_id` BIGINT,
    `ip` VARCHAR(45),
    `result` ENUM('success', 'failed') NOT NULL,
    `output` TEXT,
    `duration` BIGINT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_audit_logs_user_id` (`user_id`),
    INDEX `idx_audit_logs_action` (`action`),
    INDEX `idx_audit_logs_created_at` (`created_at`),
    INDEX `idx_audit_logs_service_id` (`service_id`),
    CONSTRAINT `fk_audit_logs_user_id` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_audit_logs_service_id` FOREIGN KEY (`service_id`) REFERENCES `services`(`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_audit_logs_server_id` FOREIGN KEY (`server_id`) REFERENCES `servers`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sql_exec_history` (
    `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT,
    `username` VARCHAR(64) NOT NULL,
    `service_id` BIGINT,
    `service_code` VARCHAR(64),
    `sql_statement` TEXT NOT NULL,
    `execution_time` BIGINT,
    `result_count` INT,
    `error_message` TEXT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_sql_exec_history_user_id` (`user_id`),
    INDEX `idx_sql_exec_history_service_id` (`service_id`),
    CONSTRAINT `fk_sql_exec_history_user_id` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_sql_exec_history_service_id` FOREIGN KEY (`service_id`) REFERENCES `services`(`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `users` (`username`, `password`, `role`, `email`, `is_active`) VALUES
('admin', '$2b$12$EixZaYbB.rK4fl8x2q7Meu6Q6D2V5fF5Q5Q5Q5Q5Q5Q5Q5Q5Q5Q', 'ADMIN', 'admin@example.com', 1) ON DUPLICATE KEY UPDATE role='ADMIN';

INSERT INTO `servers` (`hostname`, `ip`, `ssh_port`, `username`, `password`, `os_type`) VALUES
('localhost', '127.0.0.1', 22, 'root', '', 'LINUX') ON DUPLICATE KEY UPDATE hostname='localhost';