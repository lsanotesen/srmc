"""迁移 0024：新增 host:manage / backup:manage 独立权限并授予相应角色（安全修复 point 4）

背景：方案 C 收窄了 user_manage 的映射（仅 user:* / role:*），而 server.py 的增删改
      与 backup.py 的全部路由原本复用 user_manage 守卫，导致组织管理员连带失去
      服务器管理与数据库备份能力。本迁移新增两个独立权限码 host:manage、
      backup:manage，并授予：

      - 组织管理员：恢复服务器管理与数据库备份能力（point 4）；
        同时组织管理员仍无任何 user:* / role:* 权限，无法管理用户与角色。
      - 超级管理员：补齐其“全部系统权限”基线在数据库中的表示（运行时本已短路拥有）。

部门管理员 / 部门成员 / 只读用户不授予，保持不变。

只操作 permission 与 role_permissions 数据，不改表结构，不动其他角色。

注意：本迁移是一次性数据修正，故意不加入 startup.sh 自动执行，
      以免每次重启覆盖管理员在“功能权限分配”页面上的后续配置。

用法：
    python -m migrations.0024_grant_org_admin_host_backup           # 应用（幂等）
    python -m migrations.0024_grant_org_admin_host_backup rollback  # 按快照回滚

回滚快照：migrations/_snapshots/before_0024_host_backup_20261009.json
"""
import json
import os
import sys

from core.database import SessionLocal
from models.role import Role
from models.permission import Permission
from models.role_permission import RolePermission

# 需要确保存在并授予的权限（新码 resource:action）
PERMISSIONS = [
    {"resource": "host", "action": "manage", "name": "管理主机",
     "description": "新增/编辑/删除主机（服务器）"},
    {"resource": "backup", "action": "manage", "name": "管理数据库备份",
     "description": "配置/执行/下载/恢复/删除数据库备份"},
]

# 角色 → 需要授予的权限码
GRANTS = {
    "组织管理员": ["host:manage", "backup:manage"],
    "超级管理员": ["host:manage", "backup:manage"],
}

SNAPSHOT_PATH = os.path.join(
    os.path.dirname(__file__), "_snapshots",
    "before_0024_host_backup_20261009.json",
)


def _ensure_permission(db, pd):
    """确保权限行存在，返回 Permission"""
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
            code_to_id_before = {
                f"{p.resource}:{p.action}": p.id for p in db.query(Permission).all()
            }
            missing_codes = [
                f"{pd['resource']}:{pd['action']}"
                for pd in PERMISSIONS
                if f"{pd['resource']}:{pd['action']}" not in code_to_id_before
            ]
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

        # 2. 确保权限行存在
        perm_id_by_code = {}
        for pd in PERMISSIONS:
            perm, created = _ensure_permission(db, pd)
            code = f"{pd['resource']}:{pd['action']}"
            perm_id_by_code[code] = perm.id
            print(f"[apply] permission {'created' if created else 'exists'}: "
                  f"{code} (id={perm.id})")

        # 3. 按角色授予（幂等，跳过已存在关联）
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
            for code in codes:
                pid = perm_id_by_code.get(code)
                if pid is None or pid in existing_ids:
                    continue
                db.add(RolePermission(role_id=role.id, permission_id=pid))
                added += 1
            total += added
            print(f"[apply] {role_name}: granted {added} new rows")

        db.commit()
        print(f"Migration 0024 applied, total granted = {total}")
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
        # 1. 精确恢复各角色的 role_permissions 到快照集合
        for role_name, info in snap["roles"].items():
            role_id = int(info["role_id"])
            db.query(RolePermission).filter(
                RolePermission.role_id == role_id
            ).delete(synchronize_session=False)
            for pid in info["permission_ids"]:
                db.add(RolePermission(role_id=role_id, permission_id=pid))
            print(f"[rollback] {role_name}: restored {len(info['permission_ids'])} rows")

        # 2. 删除本迁移新建、且无任何角色引用的权限行
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
        print("Migration 0024 rollback completed")
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