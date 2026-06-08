from enum import Enum

class ServiceType(str, Enum):
    APP = "APP"
    NGINX = "NGINX"
    REDIS = "REDIS"
    MYSQL = "MYSQL"
    KINGBASE = "KINGBASE"
    DAMENG = "DAMENG"
    ELASTICSEARCH = "ELASTICSEARCH"
    RABBITMQ = "RABBITMQ"
    OTHER = "OTHER"

class Capability(str, Enum):
    STATUS_MONITOR = "status_monitor"
    START_STOP = "start_stop"
    RESTART = "restart"
    LOG_VIEW = "log_view"
    WEB_SHELL = "web_shell"
    SQL_CONSOLE = "sql_console"
    DATABASE_LIST = "database_list"
    USER_MANAGEMENT = "user_management"
    CONNECTION_MONITOR = "connection_monitor"
    BACKUP_RESTORE = "backup_restore"
    CLUSTER_STATUS = "cluster_status"
    NODE_MANAGEMENT = "node_management"
    INDEX_MANAGEMENT = "index_management"
    DSL_QUERY = "dsl_query"
    SNAPSHOT_MANAGEMENT = "snapshot_management"

SERVICE_TYPE_CAPABILITIES = {
    ServiceType.APP: [
        Capability.STATUS_MONITOR,
        Capability.START_STOP,
        Capability.RESTART,
        Capability.LOG_VIEW,
        Capability.WEB_SHELL
    ],
    ServiceType.NGINX: [
        Capability.STATUS_MONITOR,
        Capability.START_STOP,
        Capability.RESTART,
        Capability.LOG_VIEW,
        Capability.WEB_SHELL
    ],
    ServiceType.REDIS: [
        Capability.STATUS_MONITOR,
        Capability.START_STOP,
        Capability.RESTART,
        Capability.LOG_VIEW
    ],
    ServiceType.MYSQL: [
        Capability.STATUS_MONITOR,
        Capability.SQL_CONSOLE,
        Capability.DATABASE_LIST,
        Capability.USER_MANAGEMENT,
        Capability.CONNECTION_MONITOR,
        Capability.BACKUP_RESTORE
    ],
    ServiceType.KINGBASE: [
        Capability.STATUS_MONITOR,
        Capability.SQL_CONSOLE,
        Capability.DATABASE_LIST,
        Capability.USER_MANAGEMENT,
        Capability.CONNECTION_MONITOR
    ],
    ServiceType.DAMENG: [
        Capability.STATUS_MONITOR,
        Capability.SQL_CONSOLE,
        Capability.DATABASE_LIST,
        Capability.USER_MANAGEMENT,
        Capability.CONNECTION_MONITOR
    ],
    ServiceType.ELASTICSEARCH: [
        Capability.STATUS_MONITOR,
        Capability.CLUSTER_STATUS,
        Capability.NODE_MANAGEMENT,
        Capability.INDEX_MANAGEMENT,
        Capability.DSL_QUERY,
        Capability.SNAPSHOT_MANAGEMENT
    ],
    ServiceType.RABBITMQ: [
        Capability.STATUS_MONITOR,
        Capability.START_STOP,
        Capability.RESTART,
        Capability.LOG_VIEW
    ],
    ServiceType.OTHER: [
        Capability.STATUS_MONITOR
    ]
}

ROLE_PERMISSIONS = {
    "ADMIN": [
        "service_view", "service_operate", "service_manage", "webshell", "sql_execute",
        "log_view", "log_download", "import", "export", "audit_view",
        "user_manage", "system_settings", "project_manage", "project_view"
    ],
    "OPS": [
        "service_view", "service_operate", "service_manage", "webshell", "sql_execute",
        "log_view", "log_download", "import", "export", "audit_view",
        "project_manage", "project_view"
    ],
    "DEV": [
        "service_view", "log_view", "webshell", "sql_read", "project_view"
    ],
    "READONLY": [
        "service_view", "log_view", "project_view"
    ]
}
