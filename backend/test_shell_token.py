import asyncio
import websockets
from jose import jwt
from datetime import datetime, timedelta
import os
import sys
sys.path.insert(0, '/home/isi/srmc/backend')
from core.config import settings

async def test_websocket():
    # 生成一个有效token
    payload = {
        "sub": "admin",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    print(f"Generated token: {token[:20]}...")
    
    try:
        async with websockets.connect(f"ws://localhost:8000/api/shell/ws/1?token={token}") as websocket:
            print("Connected to WebSocket")
            
            # 接收欢迎消息
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            print(f"Received: {message}")
            
            # 发送命令
            await websocket.send("ls")
            print("Sent command: ls")
            
            # 接收响应
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            print(f"Response: {response}")
            
    except asyncio.TimeoutError:
        print("Timeout waiting for response")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_websocket())
