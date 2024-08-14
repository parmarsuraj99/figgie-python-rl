import asyncio
import json
import websockets
from datetime import datetime
import os


def log_to_file(player_id, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_dir = "player_logs"
    os.makedirs(log_dir, exist_ok=True)
    filename = os.path.join(log_dir, f"{player_id}_log.txt")
    with open(filename, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


class GameClient:
    def __init__(self, player_id, uri):
        self.player_id = player_id
        self.uri = uri
        self.websocket = None

    async def connect(self):
        self.websocket = await websockets.connect(self.uri)
        log_to_file(self.player_id, f"Connected to {self.uri}")

        # Send a message to add the player
        add_player_msg = json.dumps(
            {"type": "add_player", "data": {"player_id": self.player_id}}
        )
        await self.websocket.send(add_player_msg)
        log_to_file(self.player_id, f"Sent: {add_player_msg}")

    async def send_ready(self):
        ready_msg = json.dumps(
            {"type": "player_ready", "data": {"player_id": self.player_id}}
        )
        await self.websocket.send(ready_msg)
        log_to_file(self.player_id, f"Sent: {ready_msg}")

    async def send_order(self, suit, price, is_bid):
        order = json.dumps(
            {
                "type": "place_order",
                "data": {
                    "player_id": self.player_id,
                    "suit": suit,
                    "price": price,
                    "is_bid": is_bid,
                },
            }
        )
        await self.websocket.send(order)
        log_to_file(self.player_id, f"Sent order: {order}")

    async def receive_messages(self):
        try:
            while True:
                response = await asyncio.wait_for(self.websocket.recv(), timeout=30)
                response_data = json.loads(response)
                log_to_file(self.player_id, f"Received: {response_data}")

                if "game_started" in response_data["type"]:
                    log_to_file(self.player_id, "Game started")

                if "deal_cards" in response_data["type"]:
                    log_to_file(self.player_id, "Received cards")

                if "add_order_processed" in response_data["type"]:
                    log_to_file(
                        self.player_id, f"Received order: {response_data['data']}"
                    )

                if response_data["type"] == "game_state":
                    if "countdown" in response_data["data"].keys():
                        if (
                            response_data["data"]["countdown"] == 8
                            and self.player_id == "player_1"
                        ):
                            await self.send_order("hearts", 50, True)

                # Add more specific message handling here if needed
        except asyncio.TimeoutError:
            log_to_file(
                self.player_id, "No message received for 30 seconds, closing connection"
            )
        except websockets.exceptions.ConnectionClosed:
            log_to_file(self.player_id, "Connection closed")
        finally:
            await self.websocket.close()
            log_to_file(self.player_id, "Disconnected")


async def main():
    game_id = "test_game"
    base_uri = f"ws://localhost:8000/ws"
    clients = []
    for i in range(5):
        player_id = f"player_{i+1}"
        uri = f"{base_uri}/{player_id}"
        client = GameClient(player_id, uri)
        clients.append(client)

    # Connect all clients
    await asyncio.gather(*(client.connect() for client in clients))

    # Start receiving messages for all clients
    receive_tasks = [
        asyncio.create_task(client.receive_messages()) for client in clients
    ]

    # Wait for 5 seconds
    await asyncio.sleep(5)

    # Send ready signal for all clients
    await asyncio.gather(*(client.send_ready() for client in clients))

    # Wait for all receive tasks to complete
    await asyncio.gather(*receive_tasks)


if __name__ == "__main__":
    # Remove the log folder
    os.system("rm -rf player_logs")
    asyncio.run(main())
