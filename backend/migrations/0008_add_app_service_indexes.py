"""
迁移脚本：为 app_services 表添加关键索引

背景：
- project_id 单列索引已存在（idx_project），无需重复创建
- 多条件组合查询（project_id + subsystem_id + group_id）无复合索引，无法利用索引合并
- owner 字段无索引，按负责人搜索时全表扫描

新增索引：
1. idx_app_service_tree   - (project_id, subsystem_id, group_id) 复合索引
2. idx_app_service_owner  - owner 单列索引（搜索场景）

注：MySQL 不支持 CREATE INDEX IF NOT EXISTS 语法，通过 inspector 预检查跳过。

执行：docker exec srmc-backend python -m migrations.0008_add_app_service_indexes
"""
from sqlalchemy import create_engine, inspect, text
from core.config import settings

engine = create_engine(settings.DATABASE_URL)

# 待创建的索引列表：(索引名, SQL) - 不使用 IF NOT EXISTS（MySQL 不支持）
INDEXES = [
    (
        "idx_app_service_tree",
        "CREATE INDEX idx_app_service_tree ON app_services (project_id, subsystem_id, group_id)"
    ),
    (
        "idx_app_service_owner",
        "CREATE INDEX idx_app_service_owner ON app_services (owner)"
    ),
]


def get_existing_indexes(engine, table_name: str) -> set:
    """获取表上已存在的索引名集合"""
    inspector = inspect(engine)
    indexes = inspector.get_indexes(table_name)
    return {idx['name'] for idx in indexes if idx.get('name')}


def main():
    table_name = 'app_services'
    existing = get_existing_indexes(engine, table_name)
    print(f"[migration] 表 {table_name} 现有索引: {sorted(existing)}")

    with engine.connect() as conn:
        for index_name, sql in INDEXES:
            if index_name in existing:
                print(f"[migration] 跳过已存在索引: {index_name}")
                continue
            print(f"[migration] 创建索引: {index_name}")
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"[migration] ✓ 创建成功: {index_name}")
            except Exception as e:
                # 索引已存在（1061 错误码）则跳过
                if "1061" in str(e) or "Duplicate key name" in str(e):
                    print(f"[migration] 跳过已存在索引（DB 报错）: {index_name}")
                    conn.rollback()
                else:
                    print(f"[migration] ✗ 创建失败 {index_name}: {e}")
                    raise

    # 验证
    new_existing = get_existing_indexes(engine, table_name)
    print(f"\n[migration] 完成后索引: {sorted(new_existing)}")
    print("\n[migration] 验证示例（在 mysql 客户端执行查看是否走索引）：")
    print("  EXPLAIN SELECT * FROM app_services WHERE project_id = 1;")
    print("  EXPLAIN SELECT * FROM app_services WHERE project_id = 1 AND subsystem_id = 2 AND group_id = 3;")


if __name__ == "__main__":
    main()
    print("[migration] 0008_add_app_service_indexes 完成")
