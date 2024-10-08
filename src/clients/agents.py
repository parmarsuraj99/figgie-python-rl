import asyncio
import json
import os
import random
from collections import deque
from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

import openai
import websockets


def log_to_file(player_id, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_dir = "player_logs"
    os.makedirs(log_dir, exist_ok=True)
    filename = os.path.join(log_dir, f"{player_id}_log.txt")
    with open(filename, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


class GameClient:
    def __init__(self, player_id, game_uri):
        self.player_id = player_id
        self.uri = game_uri + f"/{player_id}"
        self.websocket = None
        self.game_state = {}
        self.cards = {}
        self.cash = 0
        self.order_queue = asyncio.Queue()

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.uri)
            log_to_file(self.player_id, f"Connected to {self.uri}")

            add_player_msg = json.dumps(
                {"type": "add_player", "data": {"player_id": self.player_id}}
            )
            await self.websocket.send(add_player_msg)
            log_to_file(self.player_id, f"Sent: {add_player_msg}")
        except Exception as e:
            log_to_file(self.player_id, f"Error connecting: {str(e)}")
            raise

    async def send_ready(self):
        ready_msg = json.dumps(
            {"type": "player_ready", "data": {"player_id": self.player_id}}
        )
        await self.websocket.send(ready_msg)
        log_to_file(self.player_id, f"Sent: {ready_msg}")

    async def place_order(self, suit, price, is_bid):
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
        await self.order_queue.put(order)

    async def accept_order(self, suit, is_bid):
        accept_order = json.dumps(
            {
                "type": "accept_order",
                "data": {
                    "player_id": self.player_id,
                    "suit": suit,
                    "is_bid": is_bid,
                },
            }
        )
        await self.websocket.send(accept_order)
        log_to_file(self.player_id, f"Sent order: {accept_order}")
        await self.order_queue.put(accept_order)

    async def receive_messages(self):
        try:
            while True:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=30)
                    response_data = json.loads(response)
                    log_to_file(self.player_id, f"Received: {response_data}")

                    if response_data["type"] == "game_started":
                        log_to_file(self.player_id, "Game started")

                    elif response_data["type"] == "deal_cards":
                        self.cards = response_data["data"]["cards"]
                        self.cash = response_data["data"]["cash"]
                        log_to_file(
                            self.player_id,
                            f"Received cards: {self.cards} and cash: {self.cash}",
                        )

                    elif response_data["type"] == "game_state":
                        self.game_state = response_data["data"]
                        await self.make_decision()

                    elif response_data["type"] == "game_ended":
                        log_to_file(self.player_id, "Game ended")
                        break

                    elif response_data["type"] in [
                        "add_order_processed",
                        "accept_order_processed",
                    ]:
                        log_to_file(
                            self.player_id, f"Order processed: {response_data['data']}"
                        )
                        await self.order_queue.get()  # Remove the processed order from the queue

                    elif response_data["type"] == "transaction_processed":
                        await self.update_after_transaction(response_data["data"])

                except asyncio.TimeoutError:
                    log_to_file(
                        self.player_id,
                        "No response from server, checking order queue...",
                    )
                    if not self.order_queue.empty():
                        last_order = await self.order_queue.get()
                        log_to_file(
                            self.player_id, f"Resending last order: {last_order}"
                        )
                        await self.websocket.send(last_order)

        except websockets.exceptions.ConnectionClosed:
            log_to_file(self.player_id, "Connection closed")
        except Exception as e:
            log_to_file(self.player_id, f"Error in receive_messages: {str(e)}")
        finally:
            await self.websocket.close()
            log_to_file(self.player_id, "Disconnected")

    async def make_decision(self):
        pass

    async def update_after_transaction(self, transaction_data):
        if transaction_data["from"] == self.player_id:
            self.cash += transaction_data["amount"]
            self.cards[transaction_data["suit"]] -= 1
        elif transaction_data["to"] == self.player_id:
            self.cash -= transaction_data["amount"]
            self.cards[transaction_data["suit"]] = (
                self.cards.get(transaction_data["suit"], 0) + 1
            )
        log_to_file(
            self.player_id,
            f"Updated after transaction: Cards: {self.cards}, Cash: {self.cash}",
        )


class AggressiveTrader(GameClient):
    async def make_decision(self):
        if not self.game_state or "orderbook" not in self.game_state:
            return

        for suit in ["hearts", "diamonds", "clubs", "spades"]:
            bid = self.game_state["orderbook"]["bids"].get(suit, {"price": -1})["price"]
            ask = self.game_state["orderbook"]["asks"].get(suit, {"price": -1})["price"]

            if random.random() < 0.5:  # 50% chance to make a move
                if self.cards.get(suit, 0) > 0:
                    # If we have the card, try to sell at a higher price
                    if bid == -1:
                        sell_price = random.randint(5, 20)
                    else:
                        sell_price = bid + random.randint(1, 5)
                    await self.place_order(suit, sell_price, False)
                elif self.cash >= 1:
                    # If we don't have the card and have enough cash, try to buy
                    if ask == -1:
                        buy_price = random.randint(1, 15)
                    else:
                        buy_price = max(1, ask - random.randint(1, 5))
                    await self.place_order(suit, buy_price, True)

            # Randomly accept orders
            if random.random() < 0.3:  # 30% chance to accept an order
                if self.cards.get(suit, 0) > 0 and bid > 0:
                    await self.accept_order(suit, True)  # Accept a bid (sell)
                elif self.cash >= ask and ask > 0:
                    await self.accept_order(suit, False)  # Accept an ask (buy)


class SpeculativeAccumulator(GameClient):
    def __init__(self, player_id, uri):
        super().__init__(player_id, uri)
        self.target_suit = None

    async def make_decision(self):
        if not self.game_state or "orderbook" not in self.game_state:
            return

        if not self.target_suit:
            self.target_suit = random.choice(["hearts", "diamonds", "clubs", "spades"])
            log_to_file(self.player_id, f"Chosen target suit: {self.target_suit}")

        bid = self.game_state["orderbook"]["bids"].get(self.target_suit, {"price": -1})[
            "price"
        ]
        ask = self.game_state["orderbook"]["asks"].get(self.target_suit, {"price": -1})[
            "price"
        ]

        if random.random() < 0.8:  # 80% chance to make a move
            if ask > 0 and self.cash >= ask:
                # Try to buy at ask price or slightly higher
                buy_price = ask + random.randint(0, 2)
                await self.place_order(self.target_suit, buy_price, True)
            elif self.cash >= 1:
                # Place a competitive bid
                if bid == -1:
                    buy_price = random.randint(1, 15)  # Set an initial price if no bids
                else:
                    buy_price = bid + random.randint(1, 3)
                await self.place_order(self.target_suit, buy_price, True)

        # Randomly sell other suits
        for suit in ["hearts", "diamonds", "clubs", "spades"]:
            if (
                suit != self.target_suit
                and self.cards.get(suit, 0) > 0
                and random.random() < 0.4
            ):
                if bid == -1:
                    sell_price = random.randint(
                        5, 20
                    )  # Set an initial price if no bids
                else:
                    sell_price = max(bid, bid + random.randint(1, 5))
                await self.place_order(suit, sell_price, False)


class MarketMaker(GameClient):
    async def make_decision(self):
        if not self.game_state or "orderbook" not in self.game_state:
            return

        for suit in ["hearts", "diamonds", "clubs", "spades"]:
            bid = self.game_state["orderbook"]["bids"].get(suit, {"price": -1})["price"]
            ask = self.game_state["orderbook"]["asks"].get(suit, {"price": -1})["price"]

            if random.random() < 0.9:  # 90% chance to make a move
                spread = random.randint(2, 5)

                if bid == -1 and ask == -1:
                    # No existing orders, create a new spread
                    new_bid = random.randint(1, 10)
                    new_ask = new_bid + spread
                elif bid == -1:
                    # No existing bid, create a new one below the ask
                    new_bid = max(1, ask - spread)
                    new_ask = ask
                elif ask == -1:
                    # No existing ask, create a new one above the bid
                    new_bid = bid
                    new_ask = bid + spread
                else:
                    # Both bid and ask exist, try to improve the spread
                    new_bid = min(bid + 1, ask - spread)
                    new_ask = max(ask - 1, bid + spread)

                if new_bid < 0 or new_ask < 0:
                    continue

                if self.cash >= new_bid:
                    await self.place_order(suit, new_bid, True)
                if self.cards.get(suit, 0) > 0:
                    await self.place_order(suit, new_ask, False)

            # Randomly accept orders to balance inventory
            if random.random() < 0.2:  # 20% chance to accept an order
                if self.cards.get(suit, 0) > 2 and bid > 0:
                    await self.accept_order(suit, True)  # Accept a bid (sell)
                elif self.cards.get(suit, 0) < 2 and self.cash >= ask and ask > 0:
                    await self.accept_order(suit, False)  # Accept an ask (buy)
