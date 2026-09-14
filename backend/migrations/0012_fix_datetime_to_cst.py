# -*- coding: utf-8 -*-
"""
迁移脚本：修正历史时间为北京时间(UTC+8)

背景：backend / mysql 容器此前时区为 UTC，datetime 列存的是 UTC 墙上时间，
前端按北京时间(UTC+8)展示导致少 8 小时。本脚本把所有 DATETIME 列统一 +8 小时。

注意：
- 仅处理 DATA_TYPE='datetime' 的列（本项目无 timestamp 列；timestamp 会随会话
  时区自动转换，不能手动 +8，否则双重偏移）。
- 每张表用一条 UPDATE 同时 SET 所有时间列，避免 updated_at 的
  ON UPDATE CURRENT_TIMESTAMP 先被刷成当前时间、再被错误 +8。
- 只能执行一次！默认 dry-run，传入 apply 参数才真正写库：
    python migrations/0012_fix_datetime_to_cst.py          # 预览
    python migrations/0012_fix_datetime_to_cst.py apply    # 执行
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine
from sqlalchemy import text

APPLY = len(sys.argv) > 1 and sys.argv[1] == "apply"


def main():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT TABLE_NAME, COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND DATA_TYPE = 'datetime'
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """)).fetchall()

        # 按表分组
        tables = {}
        for table_name, col_name in rows:
            tables.setdefault(table_name, []).append(col_name)

        print(f"共 {len(tables)} 张表、{len(rows)} 个 datetime 列待处理；模式：{'APPLY' if APPLY else 'DRY-RUN'}\n")

        for table_name, cols in tables.items():
            set_clause = ", ".join(f"`{c}` = `{c}` + INTERVAL 8 HOUR" for c in cols)
            sql = f"UPDATE `{table_name}` SET {set_clause}"
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).scalar()
            print(f"[{'执行' if APPLY else '预览'}] {table_name} ({cnt} 行): {', '.join(cols)}")
            if APPLY:
                conn.execute(text(sql))

        if APPLY:
            conn.commit()
            print("\n已提交：所有 datetime 列 +8 小时完成。")
        else:
            conn.rollback()
            print("\nDRY-RUN 未写库。确认无误后执行： python migrations/0012_fix_datetime_to_cst.py apply")


if __name__ == "__main__":
    main()
