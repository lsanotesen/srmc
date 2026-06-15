from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session
from models.user import User
from schemas.user import LoginRequest
from core.config import settings
from utils.crypto import decrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def authenticate_user(db: Session, login_request: LoginRequest):
    user = db.query(User).filter(User.username == login_request.username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(login_request.password, user.password):
        return None
    return user

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None