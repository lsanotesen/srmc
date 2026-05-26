from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import base64
from core.config import settings

def encrypt(data: str) -> str:
    key = base64.b64decode(settings.SECRET_KEY)
    iv = b'\x00' * 12
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data.encode()) + padder.finalize()
    
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    return base64.b64encode(ciphertext).decode()

def decrypt(data: str) -> str:
    key = base64.b64decode(settings.SECRET_KEY)
    iv = b'\x00' * 12
    
    ciphertext = base64.b64decode(data)
    
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    
    return data.decode()
