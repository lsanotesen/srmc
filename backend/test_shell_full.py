import asyncio
import websockets
import requests

async def test_websocket():
    # 先获取token
    try:
        login_response = requests.post(
            "http://localhost:8000/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        print(f"Login response: {login_response.status_code}")
        if login_response.status_code == 200:
            token = login_response.json()["data"]["access_token"]
            print(f"Got token: {token[:20]}...")
            
            # 测试WebSocket
            async with websockets.connect(f"ws://localhost:8000/api/shell/ws/1?token={token}") as websocket:
                print("Connected to WebSocket")
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5)
                        print(f"Received: {message}")
                        break
                    except asyncio.TimeoutError:
                        print("Timeout waiting for message")
                        break
        else:
            print(f"Login failed: {login_response.text}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_websocket())
