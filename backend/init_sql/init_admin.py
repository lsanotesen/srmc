import os
import sys
sys.path.insert(0, '/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from models.user import User

def init_admin():
    database_url = os.getenv('DATABASE_URL', 'mysql+pymysql://srmc:srmc123@mysql:3306/srmc?charset=utf8mb4')
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        admin_user = db.query(User).filter(User.username == 'admin').first()
        
        if admin_user:
            db.execute(
                text("UPDATE users SET role = :role, is_active = :is_active WHERE id = :user_id"),
                {
                    'role': 'ADMIN',
                    'is_active': True,
                    'user_id': admin_user.id
                }
            )
            print("Admin user already exists, skipping password update")
        else:
            admin_user = User(
                username='admin',
                password='$2b$12$UkjGjVJJr59b4QDdKChcTedlPhESbyP5rTv8k1oCDdwn/Quz0TbSy',
                role='ADMIN',
                email='admin@example.com',
                is_active=True
            )
            db.add(admin_user)
        
        db.commit()
        print("Admin user initialized successfully")
    except Exception as e:
        print(f"Error initializing admin user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_admin()