import asyncio
import websockets

async def test_websocket():
    try:
        async with websockets.connect("ws://localhost:8000/api/shell/ws/1?token=test-token") as websocket:
            print("Connected to WebSocket")
            message = await websocket.recv()
            print(f"Received: {message}")
            await websocket.send("ls")
            response = await websocket.recv()
            print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_websocket())
