"""迁移 0025：project_permissions 增加高风险能力独立授权字段

背景：项目共享统一为「只读(READ)/读写(EDIT/MANAGE)」两级，但 WebShell、Root 登录、
      SFTP、服务删除、服务发布、备份恢复属于高风险能力，不得只凭「读写」共享自动开放。
      本迁移为 project_permissions 增加 6 个布尔字段（默认 0），实现按共享对象的独立授权。

      本迁移只新增列，不改动任何既有共享记录（不提升、不清空），
      既有记录的高风险能力一律默认关闭。

用法：
    python -m migrations.0025_project_permission_high_risk            # 应用（幂等）
    python -m migrations.0025_project_permission_high_risk rollback   # 回滚（删除新增列）
"""
import json
import os
import sys

from sqlalchemy import create_engine, inspect, text
from core.config import settings

engine = create_engine(settings.DATABASE_URL)

NEW_COLUMNS = [
    ("allow_webshell", "允许 WebShell 远程终端"),
    ("allow_root", "允许 Root 登录"),
    ("allow_sftp", "允许 SFTP 文件操作"),
    ("allow_service_delete", "允许服务删除"),
    ("allow_service_deploy", "允许服务发布"),
    ("allow_backup", "允许备份/恢复"),
]

SNAPSHOT_PATH = os.path.join(
    os.path.dirname(__file__), "_snapshots",
    "before_0025_project_permission_high_risk.json",
)


def apply():
    inspector = inspect(engine)
    existing = [c["name"] for c in inspector.get_columns("project_permissions")]

    # 记录快照（首次应用前）
    if not os.path.exists(SNAPSHOT_PATH):
        os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump({"columns_before": existing}, f, ensure_ascii=False, indent=2)
        print(f"[snapshot] {SNAPSHOT_PATH}")

    with engine.connect() as conn:
        for col, _comment in NEW_COLUMNS:
            if col in existing:
                print(f"[skip] column exists: {col}")
                continue
            conn.execute(
                text(f"ALTER TABLE project_permissions ADD COLUMN {col} TINYINT(1) NOT NULL DEFAULT 0")
            )
            print(f"[apply] added column: {col}")
        conn.commit()
    print("Migration 0025 applied")


def rollback():
    with engine.connect() as conn:
        inspector = inspect(engine)
        existing = [c["name"] for c in inspector.get_columns("project_permissions")]
        for col, _comment in NEW_COLUMNS:
            if col not in existing:
                print(f"[skip] column absent: {col}")
                continue
            conn.execute(text(f"ALTER TABLE project_permissions DROP COLUMN {col}"))
            print(f"[rollback] dropped column: {col}")
        conn.commit()
    print("Migration 0025 rollback completed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        apply()