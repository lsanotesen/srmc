# -*- coding: utf-8 -*-
"""
迁移脚本：SubsystemGroupRelation 表加 display_order 字段
- 每个子系统内部分类独立排序，支持不同项目不同顺序
- 回填已有数据：按 relation.id 递增顺序赋值（保持当前显示顺序）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine
from sqlalchemy import text


def migrate():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # 1. 加 display_order 字段
            conn.execute(text("""
                ALTER TABLE subsystem_group_relations
                ADD COLUMN display_order INT DEFAULT 0 COMMENT '子系统内显示顺序'
                AFTER group_id
            """))

            # 2. 回填已有数据：按 relation.id 递增顺序赋值
            #    同一子系统内 id 小的先插入 = 先关联 = 应该排在前面
            conn.execute(text("""
                UPDATE subsystem_group_relations r
                JOIN (
                    SELECT id,
                           ROW_NUMBER() OVER (PARTITION BY subsystem_id ORDER BY id) - 1 AS rn
                    FROM subsystem_group_relations
                ) t ON r.id = t.id
                SET r.display_order = t.rn
            """))

            trans.commit()
            print("Migration completed: subsystem_group_relations.display_order added and backfilled")
        except Exception as e:
            trans.rollback()
            print(f"Migration failed: {e}")
            raise


def rollback():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("""
                ALTER TABLE subsystem_group_relations
                DROP COLUMN display_order
            """))
            trans.commit()
            print("Rollback completed: display_order column removed")
        except Exception as e:
            trans.rollback()
            print(f"Rollback failed: {e}")
            raise


if __name__ == "__main__":
    migrate()
