import logging
import sys
from uuid import uuid4

import fasthtml.common as fhc
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from src.backend.websocket_game import WebSocketGame

# logger = logging.getLogger("uvicorn.error")
# logger.setLevel(logging.DEBUG)


async def get_game_ui():
    with open("src/backend/static/game_ui.html", "r") as file:
        return file.read()  # Return the raw HTML content as a string


def setup_routes(app: FastAPI, game: WebSocketGame):
    @app.get("/")
    async def get_ui():
        return HTMLResponse(
            content=await get_game_ui()
        )  # Directly return HTMLResponse with the content

    @app.websocket("/ws/ui")
    async def websocket_ui_endpoint(websocket: WebSocket):
        await game.handle_ui_connection(websocket)


app = FastAPI()
game = WebSocketGame(game_id=str(uuid4()))
setup_routes(app, game)


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

    uvicorn.run(
        "app:app",
        host="localhost",
        port=8000,
        reload=True,
        log_level="info",
        workers=2,
    )
