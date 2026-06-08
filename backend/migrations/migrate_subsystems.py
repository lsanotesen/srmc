"""
数据迁移脚本：为现有数据添加子系统和程序分类支持
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings
from sqlalchemy.orm import sessionmaker
from models.project import Project
from models.subsystem import Subsystem
from models.service_group import ServiceGroup
from models.app_service import AppService

def migrate():
    """执行数据迁移"""
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("开始数据迁移...")
        
        # 1. 创建表
        print("创建子系统表...")
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS subsystems (
                id INT AUTO_INCREMENT PRIMARY KEY,
                project_id BIGINT NOT NULL,
                subsystem_name VARCHAR(100) NOT NULL COMMENT '子系统名称',
                subsystem_code VARCHAR(50) NOT NULL UNIQUE COMMENT '子系统编码',
                display_order INT DEFAULT 0 COMMENT '显示顺序',
                description TEXT COMMENT '描述',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                INDEX idx_project_id (project_id),
                INDEX idx_subsystem_code (subsystem_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='子系统表'
        """))
        
        print("创建程序分类表...")
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS service_groups (
                id INT AUTO_INCREMENT PRIMARY KEY,
                subsystem_id INT NOT NULL,
                group_name VARCHAR(100) NOT NULL COMMENT '分类名称',
                group_code VARCHAR(50) NOT NULL COMMENT '分类编码',
                display_order INT DEFAULT 0 COMMENT '显示顺序',
                description TEXT COMMENT '描述',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (subsystem_id) REFERENCES subsystems(id) ON DELETE CASCADE,
                UNIQUE KEY uk_subsystem_code (subsystem_id, group_code),
                INDEX idx_subsystem_id (subsystem_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='程序分类表'
        """))
        
        print("为 app_services 表添加新字段...")
        # 检查字段是否已存在
        result = session.execute(text("SHOW COLUMNS FROM app_services LIKE 'subsystem_id'"))
        if not result.fetchone():
            session.execute(text("""
                ALTER TABLE app_services 
                ADD COLUMN subsystem_id INT NULL COMMENT '子系统ID',
                ADD COLUMN group_id INT NULL COMMENT '程序分类ID',
                ADD FOREIGN KEY (subsystem_id) REFERENCES subsystems(id) ON DELETE SET NULL,
                ADD FOREIGN KEY (group_id) REFERENCES service_groups(id) ON DELETE SET NULL,
                ADD INDEX idx_subsystem_id (subsystem_id),
                ADD INDEX idx_group_id (group_id)
            """))
        
        session.commit()
        
        # 2. 为每个项目创建默认子系统
        print("为项目创建默认子系统...")
        projects = session.query(Project).all()
        for project in projects:
            existing = session.query(Subsystem).filter(
                Subsystem.project_id == project.id
            ).first()
            if not existing:
                subsystem = Subsystem(
                    project_id=project.id,
                    subsystem_name='默认子系统',
                    subsystem_code=f'DEFAULT_{project.id}',
                    display_order=0,
                    description='系统升级自动创建'
                )
                session.add(subsystem)
                session.flush()
                print(f"  - 为项目 '{project.name}' 创建默认子系统")
        
        session.commit()
        
        # 3. 为每个子系统创建默认分类
        print("为子系统创建默认分类...")
        subsystems = session.query(Subsystem).all()
        for subsystem in subsystems:
            existing = session.query(ServiceGroup).filter(
                ServiceGroup.subsystem_id == subsystem.id
            ).first()
            if not existing:
                group = ServiceGroup(
                    subsystem_id=subsystem.id,
                    group_name='默认分类',
                    group_code='DEFAULT_GROUP',
                    display_order=0,
                    description='系统升级自动创建'
                )
                session.add(group)
                session.flush()
                print(f"  - 为子系统 '{subsystem.subsystem_name}' 创建默认分类")
        
        session.commit()
        
        # 4. 将现有服务关联到默认子系统和分类
        print("将现有服务关联到默认子系统和分类...")
        services = session.query(AppService).filter(
            AppService.subsystem_id.is_(None)
        ).all()
        
        for service in services:
            # 获取该项目的默认子系统
            subsystem = session.query(Subsystem).filter(
                Subsystem.project_id == service.project_id
            ).first()
            
            if subsystem:
                # 获取该子系统的默认分类
                group = session.query(ServiceGroup).filter(
                    ServiceGroup.subsystem_id == subsystem.id
                ).first()
                
                if group:
                    service.subsystem_id = subsystem.id
                    service.group_id = group.id
                    print(f"  - 服务 '{service.func_desc}' 已关联到默认子系统和分类")
        
        session.commit()
        
        print("数据迁移完成！")
        print(f"  - 项目数: {len(projects)}")
        print(f"  - 子系统数: {session.query(Subsystem).count()}")
        print(f"  - 程序分类数: {session.query(ServiceGroup).count()}")
        print(f"  - 已迁移服务数: {len(services)}")
        
    except Exception as e:
        print(f"数据迁移失败: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    migrate()