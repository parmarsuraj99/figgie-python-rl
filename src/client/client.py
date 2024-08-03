import websockets
import logging
import asyncio
import json
import aioconsole

logging.basicConfig(level=logging.INFO)


async def receive_messages(websocket):
    while True:
        try:
            response = await websocket.recv()
            data = json.loads(response)
            logging.info(f"Received: {data}")
            if data["type"] == "error":
                print(f"Error: {data['message']}")
                break
        except websockets.exceptions.ConnectionClosed:
            logging.info("Connection closed")
            break


async def send_messages(websocket):
    while True:
        message = await aioconsole.ainput("Enter message (or 'quit' to exit): ")
        if message.lower() == "quit":
            break
        await websocket.send(json.dumps({"type": "message", "content": message}))


async def hello():
    uri = "ws://localhost:8000/ws"  # Adjust this URL if your server is running on a different address
    async with websockets.connect(uri) as websocket:
        logging.info("Connected to WebSocket server")
        username = await aioconsole.ainput("Enter username: ")
        await websocket.send(json.dumps({"type": "join", "username": username}))

        receive_task = asyncio.create_task(receive_messages(websocket))
        send_task = asyncio.create_task(send_messages(websocket))

        await asyncio.gather(receive_task, send_task)


asyncio.get_event_loop().run_until_complete(hello())
