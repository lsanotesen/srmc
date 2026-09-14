# -*- coding: utf-8 -*-
"""
一次性数据迁移：把 subsystem_id 为空的服务挂到所属项目的"默认子系统"下，
使之前导入的服务能正确显示在项目树的程序分类中。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal
from models.subsystem import Subsystem
from models.app_service import AppService


def main():
    db = SessionLocal()
    try:
        # 项目ID -> 默认子系统ID
        default_subs = {}
        for s in db.query(Subsystem).filter(Subsystem.subsystem_name == '默认子系统').all():
            default_subs[s.project_id] = s.id

        if not default_subs:
            print("未找到任何'默认子系统'，请先执行一次导入以自动创建默认子系统")
            return

        services = db.query(AppService).filter(AppService.subsystem_id.is_(None)).all()
        updated = 0
        skipped_no_project_default = 0

        for svc in services:
            dsid = default_subs.get(svc.project_id)
            if dsid:
                svc.subsystem_id = dsid
                updated += 1
            else:
                skipped_no_project_default += 1

        db.commit()
        print(f"迁移完成: 更新 {updated} 条服务的子系统; 跳过 {skipped_no_project_default} 条(项目无默认子系统)")

        # 验证结果
        remain = db.query(AppService).filter(AppService.subsystem_id.is_(None)).count()
        print(f"剩余 subsystem_id 为空的服务数量: {remain}")
    except Exception as e:
        db.rollback()
        print(f"迁移失败: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
