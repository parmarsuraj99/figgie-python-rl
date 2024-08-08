import asyncio
from typing import Dict, List

from fastapi import WebSocket
from pydantic import BaseModel
from statics import Settings


class Player(BaseModel):
    player_id: str

    class Config:
        arbitrary_types_allowed = True


class Game(BaseModel):

    game_id: str
    started: bool = False
    timer_max = Settings.timer_countdown
    countdown: int = Settings.timer_countdown
    players: List[Player] = []

    def add_player(self, player: Player):
        # only add the unique player
        if player not in self.players:
            self.players.append(player)
        else:
            print("Player already exists")

    def remove_player(self, player_id: str):
        self.players = [
            player for player in self.players if player.player_id != player_id
        ]

    async def start(self):
        self.started = True
        self.countdown = self.timer_max
        self._timer_task = asyncio.create_task(self.run_timer())
        await self._timer_task

    async def run_timer(self):
        while self.countdown > 0:
            await asyncio.sleep(1)
            self.countdown -= 1

    def stop(self):
        if self._timer_task:
            self._timer_task.cancel()
            self.started = False
            self.countdown = self.timer_max

    class Config:
        arbitrary_types_allowed = True


class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, "WebSocket"] = {}

    async def connect(self, player_id: str, websocket: "WebSocket"):
        await websocket.accept()
        self.connections[player_id] = websocket

    def disconnect(self, player_id: str):
        self.connections.pop(player_id, None)

    async def send_message(self, player_id: str, message: str):
        if websocket := self.connections.get(player_id):
            await websocket.send_text(message)


class WebSocketGame(Game):
    def __init__(self, game_id: str, websocket_manager: WebSocketManager):
        super().__init__(game_id=game_id)
        self.websocket_manager = websocket_manager

    def add_player(self, player: Player):
        super().add_player(player)
        asyncio.create_task(self.websocket_manager.connect(player.player_id, player.ws))

    def stop(self):
        super().stop()
        for player in self.players:
            self.websocket_manager.disconnect(player.player_id)

    async def send_message(self, player_id: str, message: str):
        await self.websocket_manager.send_message(player_id, message)
