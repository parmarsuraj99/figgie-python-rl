import asyncio
import json
from copy import deepcopy
from typing import Any, Callable, Dict, List, Union
from uuid import uuid4

from fastapi import FastAPI, WebSocket
from pydantic import BaseModel


class Constants:
    timer_countdown = 10


class Player(BaseModel):
    player_id: str
    ready: bool = False


class GameState(BaseModel):
    started: bool = False
    countdown: int = Constants.timer_countdown


class Game:
    def __init__(
        self,
        game_id: str,
        max_players: int = 5,
        timer_max: int = Constants.timer_countdown,
    ):
        self.game_id = game_id
        self.max_players = max_players
        self.timer_max = timer_max
        self.state = GameState(countdown=timer_max)
        self.players: Dict[str, Player] = {}
        self.event_listeners: Dict[str, List[Callable]] = {}

    def add_event_listener(self, event: str, callback: Callable):
        if event not in self.event_listeners:
            self.event_listeners[event] = []
        self.event_listeners[event].append(callback)

    def emit_event(self, event: str, data: Any):
        for callback in self.event_listeners.get(event, []):
            asyncio.create_task(callback(data))

    def add_player(self, player_id: str):
        if player_id in self.players:
            return f"Player {player_id} already in game"
        if len(self.players) < self.max_players and player_id not in self.players:
            self.players[player_id] = Player(player_id=player_id)
            self.emit_event("player_added", player_id)

    def remove_player(self, player_id: str):
        self.players.pop(player_id, None)
        self.emit_event("player_removed", player_id)

    def player_is_ready(self, player_id: str):
        player = self.players.get(player_id)
        if player:
            player.ready = True
            self.emit_event("player_ready", player_id)

    def check_all_players_ready(self):

        are_all_ready = (
            all(player.ready for player in self.players.values())
            and len(self.players) == self.max_players
        )
        return are_all_ready

    async def pre_game_countdown(self):
        for i in range(3, 0, -1):
            await asyncio.sleep(1)
            await self.broadcast({"type": "message", "data": f"Game starting in {i}"})
        await self.start_game()

    async def countdown(self):
        while self.state.countdown > 0 and self.state.started:
            await asyncio.sleep(1)
            self.state.countdown -= 1
            self.emit_event("game_state", deepcopy(self.state.__dict__))
        if self.state.started:
            await self.stop_game()

    async def stop_game(self):
        self.state.started = False
        self.state.countdown = self.timer_max
        if self.countdown_task:
            self.countdown_task.cancel()
            self.countdown_task = None
        self.emit_event("game_stopped", self.game_id)

    async def start_game(self):
        if not self.check_all_players_ready():
            return f"Not all players ready"
        self.state.started = True
        self.state.countdown = self.timer_max
        self.emit_event("game_started", self.game_id)
        self.countdown_task = asyncio.create_task(self.countdown())


class WebSocketGame(Game):
    def __init__(
        self,
        game_id: str,
        max_players: int = 5,
        timer_max: int = Constants.timer_countdown,
    ):
        super().__init__(game_id, max_players, timer_max)
        self.connections: Dict[str, WebSocket] = {}
        self.add_event_listener("player_added", self.on_player_added)
        self.add_event_listener("player_ready", self.on_player_ready)
        self.add_event_listener("game_started", self.on_game_started)
        self.add_event_listener("game_state", self.on_game_state)
        self.add_event_listener("game_stopped", self.on_game_stopped)

    async def send_message(self, player_id: str, message: dict):
        if websocket := self.connections.get(player_id):
            print(f"Sending message to {player_id}: {message}")
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for websocket in self.connections.values():
            await websocket.send_json(message)

    async def handle_message(self, player_id: str, message: str, websocket: WebSocket):
        message_type = message.get("type")
        print(f"Received message from {player_id}: {message_type}")

        if message_type == "add_player":
            print(f"Adding player {player_id}")
            self.connections[player_id] = websocket
            self.add_player(player_id)

        elif message_type == "player_ready":
            print(f"Player {player_id} is ready")
            self.player_is_ready(player_id)
            if self.check_all_players_ready():
                await self.pre_game_countdown()

    async def on_player_added(self, player_id: str):
        await self.broadcast({"type": "player_added", "data": {"player_id": player_id}})

    async def on_player_ready(self, player_id: str):
        await self.broadcast({"type": "player_ready", "data": {"player_id": player_id}})

    async def on_game_started(self, game_id: str):
        await self.broadcast({"type": "game_started", "data": {"game_id": game_id}})

    async def on_game_state(self, state: dict):
        await self.broadcast({"type": "game_state", "data": state})

    async def on_game_stopped(self, game_id: str):
        await self.broadcast({"type": "game_stopped", "data": {"game_id": game_id}})


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

    uvicorn.run("game:app", host="localhost", port=8000, reload=True, log_level="info")
