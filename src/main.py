import sys
from uuid import uuid4

from fastapi import FastAPI, WebSocket

from backend.websocket_game import WebSocketGame

sys.path.append("src")

import logging

# logger = logging.getLogger("uvicorn.error")
# logger.setLevel(logging.DEBUG)


app = FastAPI()
game = WebSocketGame(game_id=str(uuid4()))


@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: str):
    await websocket.accept()

    try:
        while True:
            message = await websocket.receive_json()
            await game.handle_message(player_id, message, websocket)
    except Exception as e:
        print(e)
    finally:
        game.connections.pop(player_id, None)
        game.remove_player(player_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=8000, reload=True, log_level="info")
