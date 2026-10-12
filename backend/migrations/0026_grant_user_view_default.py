"""迁移 0026：组织管理员 / 部门管理员默认授予用户查看权限 user:view

背景：完善用户管理的查看权限与数据范围。权限码 user:view 已存在（不新增权限码），
      本次仅为「组织管理员」「部门管理员」补齐默认查看授权：

      - 组织管理员：默认拥有 user:view，数据范围收敛到本组织（由接口层 DataScope 强制）。
      - 部门管理员：默认拥有 user:view，数据范围收敛到本部门（由接口层 DataScope 强制）。
      - 部门成员 / 只读用户：默认不授予 user:view；可在「角色管理」中自定义授权，
        授权后仍受既有数据范围限制。
      - 超级管理员：运行时短路拥有全部系统权限，无需依赖数据库关联。

本迁移只操作 role_permissions 数据，不新增/修改权限码，不改表结构，不动其他角色，
仅补齐（幂等），不会删除任何已有的自定义授权。

注意：本迁移是一次性默认基线补齐，故意不加入 startup.sh 自动执行，
      以免每次重启覆盖管理员在「功能权限分配」页面上的后续配置。

用法：
    python -m migrations.0026_grant_user_view_default           # 应用（幂等）
    python -m migrations.0026_grant_user_view_default rollback  # 按快照回滚

回滚快照：migrations/_snapshots/before_0026_user_view_20261012.json
"""
import json
import os
import sys

from core.database import SessionLocal
from models.role import Role
from models.permission import Permission
from models.role_permission import RolePermission

# 需要确保存在并授予的权限码（已存在则复用，不重复创建）
PERMISSION = {"resource": "user", "action": "view",
              "name": "查看用户", "description": "查看用户列表和详情"}

# 角色 → 需要授予的权限码（仅补齐，不删除）
GRANTS = {
    "组织管理员": ["user:view"],
    "部门管理员": ["user:view"],
}

SNAPSHOT_PATH = os.path.join(
    os.path.dirname(__file__), "_snapshots",
    "before_0026_user_view_20261012.json",
)


def _ensure_permission(db, pd):
    """确保权限行存在，返回 (Permission, created)"""
    perm = db.query(Permission).filter(
        Permission.resource == pd["resource"],
        Permission.action == pd["action"],
    ).first()
    if perm:
        return perm, False
    perm = Permission(
        resource=pd["resource"],
        action=pd["action"],
        name=pd["name"],
        description=pd.get("description"),
    )
    db.add(perm)
    db.flush()
    return perm, True


def apply():
    db = SessionLocal()
    try:
        # 1. 记录快照（仅在首次应用时写，避免重复运行覆盖原始基线）
        if not os.path.exists(SNAPSHOT_PATH):
            code = f"{PERMISSION['resource']}:{PERMISSION['action']}"
            code_to_id_before = {
                f"{p.resource}:{p.action}": p.id for p in db.query(Permission).all()
            }
            missing_codes = [] if code in code_to_id_before else [code]
            roles_snap = {}
            for role_name in GRANTS:
                role = db.query(Role).filter(Role.name == role_name).first()
                if not role:
                    continue
                roles_snap[role_name] = {
                    "role_id": role.id,
                    "permission_ids": sorted(
                        rp.permission_id
                        for rp in db.query(RolePermission)
                        .filter(RolePermission.role_id == role.id).all()
                    ),
                }
            snap = {"roles": roles_snap, "missing_codes_before": missing_codes}
            os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
            with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False, indent=2)
            print(f"[snapshot] {SNAPSHOT_PATH}")

        # 2. 确保权限行存在（已有则复用）
        perm, created = _ensure_permission(db, PERMISSION)
        code = f"{PERMISSION['resource']}:{PERMISSION['action']}"
        print(f"[apply] permission {'created' if created else 'exists'}: {code} (id={perm.id})")

        # 3. 按角色补齐授予（幂等，跳过已存在关联）
        total = 0
        for role_name, codes in GRANTS.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                print(f"[skip] 角色不存在: {role_name}")
                continue
            existing_ids = {
                rp.permission_id
                for rp in db.query(RolePermission)
                .filter(RolePermission.role_id == role.id).all()
            }
            added = 0
            for _code in codes:
                if _code != code or perm.id in existing_ids:
                    continue
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))
                added += 1
            total += added
            print(f"[apply] {role_name}: granted {added} new rows")

        db.commit()
        print(f"Migration 0026 applied, total granted = {total}")
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
        for role_name, info in snap["roles"].items():
            role_id = int(info["role_id"])
            db.query(RolePermission).filter(
                RolePermission.role_id == role_id
            ).delete(synchronize_session=False)
            for pid in info["permission_ids"]:
                db.add(RolePermission(role_id=role_id, permission_id=pid))
            print(f"[rollback] {role_name}: restored {len(info['permission_ids'])} rows")

        for code in snap.get("missing_codes_before", []):
            resource, action = code.split(":", 1)
            perm = db.query(Permission).filter(
                Permission.resource == resource,
                Permission.action == action,
            ).first()
            if not perm:
                continue
            in_use = db.query(RolePermission).filter(
                RolePermission.permission_id == perm.id
            ).first()
            if not in_use:
                db.delete(perm)
                print(f"[rollback] removed permission row {code}")

        db.commit()
        print("Migration 0026 rollback completed")
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
