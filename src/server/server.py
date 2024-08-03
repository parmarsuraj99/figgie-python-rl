from fastapi import FastAPI, WebSocket
from contextlib import asynccontextmanager
import asyncio
import logging
import time
import json
import uuid
import random
from typing import Dict, List, Any, Union, Optional, Tuple, Set

from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)


class Player(BaseModel):
    username: str
    websocket: WebSocket
    ready: bool = False

    class Config:
        arbitrary_types_allowed = True


class Game(BaseModel):
    game_id: str = str(uuid.uuid4())
    limit: int = random.choice([4, 5])
    players: List[Player] = []


app = FastAPI()
current_game = Game()


def handle_join(player: Player):
    current_players = [p.username for p in current_game.players]
    if len(current_players) == current_game.limit:
        return {"type": "error", "message": "Game is full"}
    else:
        current_game.players.append(player)
        return {
            "type": "success",
            "message": f"Joined game, total players: {len(current_game.players)}",
        }


@app.websocket("/ws")
async def on_connect(websocket: WebSocket):
    await websocket.accept()
    logging.info("WebSocket connection established")

    try:
        while True:

            data = await websocket.receive_json()
            if data["type"] == "join":
                player = Player(username=data["username"], websocket=websocket)
                response = handle_join(player)
                await websocket.send_json(response)

    finally:
        # remove player from game
        logging.info("WebSocket connection closed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
