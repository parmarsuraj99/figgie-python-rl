from .game_logic import Game, Order, Constants
from typing import Dict, List, Union
from fastapi import WebSocket, WebSocketDisconnect
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


class WebSocketGame(Game):
    def __init__(
        self,
        game_id: str,
        max_players: int = 4,
        timer_max: int = Constants.timer_countdown,
    ):
        super().__init__(game_id, max_players, timer_max)
        self.connections: Dict[str, WebSocket] = {}
        self.ui_connections: List[WebSocket] = []
        self.add_event_listener("player_added", self.on_player_added)
        self.add_event_listener("player_ready", self.on_player_ready)
        self.add_event_listener("game_started", self.on_game_started)
        self.add_event_listener("game_state", self.on_game_state)
        self.add_event_listener("game_ended", self.on_game_ended)
        self.add_event_listener("deal_cards", self.on_deal_cards)
        self.add_event_listener("add_order_processed", self.on_add_order)
        self.add_event_listener("accept_order_processed", self.on_accept_order)
        self.add_event_listener("transaction_processed", self.on_transaction_processed)

    async def send_message(self, player_id: str, message: Dict):
        if websocket := self.connections.get(player_id):
            print(f"Sending message to {player_id}: {message}")
            await websocket.send_json(message)

    async def broadcast(self, message: Dict):
        for websocket in self.connections.values():
            await websocket.send_json(message)
        for ui_websocket in self.ui_connections:
            await ui_websocket.send_json(message)

    async def handle_ui_connection(self, websocket: WebSocket):
        await websocket.accept()
        self.ui_connections.append(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            self.ui_connections.remove(websocket)

    async def handle_message(self, player_id: str, message: str, websocket: WebSocket):

        try:
            message_type = message.get("type")
            print(f"Received message from {player_id}: {message_type}")

            if message_type == "add_player":  # TODO: Change to join
                print(f"Adding player {player_id}")
                self.connections[player_id] = websocket
                self.add_player(player_id)

            elif message_type == "player_ready":
                print(f"Player {player_id} is ready")
                self.player_is_ready(player_id)
                if self.check_all_players_ready():
                    await self.pre_game_countdown()

            elif message_type == "place_order":
                print(f"Player {player_id} placed an order")
                print(message)
                order = Order(**message["data"])
                await self.process_add_order(order)

            elif message_type == "accept_order":
                print(f"Player {player_id} accepted an order")
                print(message)
                order = Order(**message["data"])
                await self.process_accept_order(order)
        except Exception as e:
            print(f"Error processing message: {e}")
            await self.send_message(player_id, {"type": "error", "message": str(e)})

    async def on_player_added(self, player_id: str):
        await self.broadcast({"type": "player_added", "data": {"player_id": player_id}})

    async def on_player_ready(self, player_id: str):
        await self.broadcast({"type": "player_ready", "data": {"player_id": player_id}})

    async def on_game_started(self, game_id: str):
        await self.broadcast({"type": "game_started", "data": {"game_id": game_id}})

    async def on_game_state(self, state: dict):
        await self.broadcast({"type": "game_state", "data": state})

    async def on_game_ended(self, state: dict):
        state.update({"game_id": self.game_id})
        await self.broadcast({"type": "game_ended", "data": state})

    async def on_deal_cards(self, data: dict):
        player_id = data["player_id"]
        message = data["data"]
        await self.send_message(player_id, {"type": "deal_cards", "data": message})

    async def on_add_order(self, data: dict):
        player_id = data["player_id"]
        message = data["message"]
        await self.send_message(
            player_id, {"type": "add_order_processed", "data": message}
        )

    async def on_accept_order(self, data: dict):
        player_id = data["player_id"]
        message = data["message"]
        await self.send_message(
            player_id, {"type": "accept_order_processed", "data": message}
        )

    async def on_transaction_processed(self, data: dict):
        message = data["message"]
        # broadcast to all players
        await self.broadcast({"type": "transaction_processed", "data": message})
