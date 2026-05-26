import os
import sys
sys.path.insert(0, '/app')

from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_admin():
    database_url = os.getenv('DATABASE_URL', 'mysql+pymysql://srmc:srmc123@mysql:3306/srmc?charset=utf8mb4')
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        admin_user = db.query(User).filter(User.username == 'admin').first()
        
        if admin_user:
            admin_user.password = pwd_context.hash('admin123')
            admin_user.role = 'ADMIN'
            admin_user.is_active = True
        else:
            admin_user = User(
                username='admin',
                password=pwd_context.hash('admin123'),
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