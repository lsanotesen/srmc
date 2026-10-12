"""迁移 0023：方案 C —— 系统角色功能权限基线与实际权限来源对齐（一次性数据修正）

目的：在把数据库角色作为运行时权限来源之前，先移除系统角色中越权/无效的权限关联。
仅删除 role_permissions 关联行，不新增权限码、不改表结构。

注意：本迁移是一次性“系统角色基线”数据对齐，故意不加入 startup.sh 自动执行，
      以免每次重启覆盖管理员在“功能权限分配”页面上的后续配置。

用法：
    python -m migrations.0023_align_planC_role_permissions           # 应用（幂等）
    python -m migrations.0023_align_planC_role_permissions rollback  # 按快照回滚

回滚快照：migrations/_snapshots/role_permissions_before_planC_20261009.json
"""
import json
import os
import sys

from core.database import SessionLocal
from models.role import Role
from models.permission import Permission
from models.role_permission import RolePermission

SNAPSHOT_PATH = os.path.join(
    os.path.dirname(__file__), "_snapshots",
    "role_permissions_before_planC_20261009.json",
)

# 各系统角色需要移除的权限码（新码 resource:action）
REMOVALS = {
    "组织管理员": [
        "department:edit", "host:reboot", "organization:edit",
        "role:view", "user:add", "user:edit", "user:view",
    ],
    "部门管理员": [
        "department:view", "organization:view", "user:edit", "user:view",
    ],
    "部门成员": [
        "department:view", "organization:view",
        "project:add", "project:edit", "project:delete", "project:share",
        "service:deploy", "service:edit-config",
    ],
    "只读用户": [
        "department:view", "organization:view",
    ],
}


def apply():
    db = SessionLocal()
    try:
        code_to_id = {f"{p.resource}:{p.action}": p.id for p in db.query(Permission).all()}
        total = 0
        for role_name, codes in REMOVALS.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                print(f"[skip] 角色不存在: {role_name}")
                continue
            ids = [code_to_id[c] for c in codes if c in code_to_id]
            if not ids:
                continue
            deleted = db.query(RolePermission).filter(
                RolePermission.role_id == role.id,
                RolePermission.permission_id.in_(ids),
            ).delete(synchronize_session=False)
            total += deleted
            print(f"[apply] {role_name}: removed {deleted} rows")
        db.commit()
        print(f"Migration 0023 applied, total removed = {total}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def rollback():
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        snap = json.load(f)
    db = SessionLocal()
    try:
        for rid, info in snap["role_permissions"].items():
            role_id = int(rid)
            db.query(RolePermission).filter(
                RolePermission.role_id == role_id
            ).delete(synchronize_session=False)
            for pid in info["permission_ids"]:
                db.add(RolePermission(role_id=role_id, permission_id=pid))
            print(f"[rollback] role {rid} ({info['role_name']}): restored {len(info['permission_ids'])} rows")
        db.commit()
        print("Migration 0023 rollback completed")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        apply()