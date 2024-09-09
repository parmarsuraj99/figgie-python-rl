import asyncio
import json
import logging
import random
from copy import deepcopy
from typing import Any, Callable, Dict, List, Union, Tuple
from uuid import uuid4

from fastapi import FastAPI, WebSocket
from pydantic import BaseModel

from .classes import Constants, GameState, Order, Player, SampleRecord, OrderBook

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


class Game:
    def __init__(
        self,
        game_id: str,
        max_players: int = 5,
        timer_max: int = Constants.timer_countdown,
        update_interval: int = Constants.update_interval,
    ):
        self.game_id = game_id
        self.max_players = max_players
        self.timer_max = timer_max
        self.state = GameState(countdown=timer_max)
        self.players: Dict[str, Player] = {}
        self.event_listeners: Dict[str, List[Callable]] = {}
        self.update_interval = update_interval
        self.ping_interval = 60
        self.pong_timeout = 30

    def get_goal_suit(self):
        goal_suit = random.choice(["hearts", "diamonds", "clubs", "spades"])
        return goal_suit

    def get_suit_distribution(self, goal_suit):
        suit2counts = {}
        goal_suit_color = Constants.suit2colors[goal_suit]
        goal_suit_counts = random.choice(Constants.goal_suit_counts)
        same_color_other_suit = [
            suit for suit in Constants.color2suits[goal_suit_color] if suit != goal_suit
        ][0]

        suit2counts[goal_suit] = goal_suit_counts
        suit2counts[same_color_other_suit] = 12

        remaining_suits = [suit for suit in Constants.suits if suit not in suit2counts]
        remaining_counts = [10, 10] if goal_suit_counts == 8 else [8, 10]
        random.shuffle(remaining_suits)
        random.shuffle(remaining_counts)

        for suit, count in zip(remaining_suits, remaining_counts):
            suit2counts[suit] = count

        return suit2counts

    def create_deck(self, suit2counts):
        all_cards = [suit for suit, count in suit2counts.items() for _ in range(count)]
        random.shuffle(all_cards)
        return all_cards

    def distribute_cards(self, all_cards):
        player2cards = {
            player_id: all_cards[i :: len(self.players)]
            for i, player_id in enumerate(self.players)
        }
        return {
            player_id: {suit: cards.count(suit) for suit in set(cards)}
            for player_id, cards in player2cards.items()
        }

    def initialize_player_cash(self):
        return {
            player_id: Constants.cash_per_player - Constants.cash_to_enter
            for player_id in self.players
        }

    async def deal_cards(self):
        self.state.goal_suit = self.get_goal_suit()
        suit2counts = self.get_suit_distribution(self.state.goal_suit)
        all_cards = self.create_deck(suit2counts)

        self.state.player2cards = self.distribute_cards(all_cards)
        self.state.player2cash = self.initialize_player_cash()
        self.state.player2card_count = {
            player_id: sum(cards.values())
            for player_id, cards in self.state.player2cards.items()
        }

        game_state = {
            "goal_suit": self.state.goal_suit,
            "suit2counts": suit2counts,
        }

        for player_id in self.players:
            player_state = {
                "cards": self.state.player2cards[player_id],
                "cash": self.state.player2cash[player_id],
            }
            self.emit_event(
                "deal_cards", {"player_id": player_id, "data": player_state}
            )

    async def process_add_order(self, order: Order):
        message = "Order added"

        if order.is_bid:
            current_ask = self.state.orderbook.asks[order.suit]
            if current_ask.price != -1 and order.price >= current_ask.price:
                # Automatic match
                await self.execute_trade(
                    order.player_id,
                    current_ask.player_id,
                    order.suit,
                    current_ask.price,
                )
                message = "Order matched and executed"
            else:
                current_bid = self.state.orderbook.bids[order.suit]
                if order.price > current_bid.price:
                    self.state.orderbook.bids[order.suit] = SampleRecord(
                        price=order.price,
                        player_id=order.player_id,
                        order_id=1,
                    )
        else:  # ask order
            current_bid = self.state.orderbook.bids[order.suit]
            if current_bid.price != -1 and order.price <= current_bid.price:
                # Automatic match
                await self.execute_trade(
                    current_bid.player_id, order.player_id, order.suit, order.price
                )
                message = "Order matched and executed"
            else:
                current_ask = self.state.orderbook.asks[order.suit]
                if current_ask.price == -1 or order.price < current_ask.price:
                    self.state.orderbook.asks[order.suit] = SampleRecord(
                        price=order.price,
                        player_id=order.player_id,
                        order_id=1,
                    )

        self.emit_event(
            "add_order_processed",
            {"player_id": order.player_id, "message": message},
        )

    async def execute_trade(self, buyer_id: str, seller_id: str, suit: str, price: int):
        if self.state.player2cards[seller_id][suit] <= 0:
            return "Trade not executed, seller does not have enough cards"
        if self.state.player2cash[buyer_id] < price:
            return "Trade not executed, buyer does not have enough cash"

        # Process the transaction
        self.state.player2cash[seller_id] += price
        self.state.player2cash[buyer_id] -= price
        self.state.player2cards[seller_id][suit] -= 1
        self.state.player2cards[buyer_id][suit] += 1
        self.state.player2card_count[seller_id] -= 1
        self.state.player2card_count[buyer_id] += 1

        # Reset the order book for this suit
        self.state.orderbook.bids[suit] = SampleRecord()
        self.state.orderbook.asks[suit] = SampleRecord()

        self.emit_event(
            "transaction_processed",
            {
                "from": seller_id,
                "to": buyer_id,
                "suit": suit,
                "amount": price,
            },
        )

        # Log the transaction for debugging
        logger.debug(
            f"Trade executed: {buyer_id} bought {suit} from {seller_id} for {price}. Current state: {self.state.model_dump()}"
        )

        return "Trade executed successfully"

    async def process_accept_order(self, order: Order):
        message = ""
        if order.is_bid:
            current_bid = self.state.orderbook.bids[order.suit]
            seller_id = order.player_id
            buyer_id = current_bid.player_id
            price = current_bid.price

            if seller_id == buyer_id:
                message = "Order not accepted, cannot accept own bid"
            elif self.state.player2cards[seller_id][order.suit] <= 0:
                message = "Order not accepted, seller does not have enough cards"
            elif self.state.player2cash[buyer_id] < price:
                message = "Order not accepted, buyer does not have enough cash"
            else:
                # Process the transaction
                self.state.player2cash[seller_id] += price
                self.state.player2cash[buyer_id] -= price
                self.state.player2cards[seller_id][order.suit] -= 1
                self.state.player2cards[buyer_id][order.suit] += 1
                self.state.player2card_count[seller_id] -= 1
                self.state.player2card_count[buyer_id] += 1
                message = "Order accepted"

                self.emit_event(
                    "transaction_processed",
                    {
                        "from": seller_id,
                        "to": buyer_id,
                        "suit": order.suit,
                        "amount": price,
                    },
                )
        else:  # ask order
            current_ask = self.state.orderbook.asks[order.suit]
            buyer_id = order.player_id
            seller_id = current_ask.player_id
            price = current_ask.price

            if buyer_id == seller_id:
                message = "Order not accepted, cannot accept own ask"
            elif self.state.player2cards[seller_id][order.suit] <= 0:
                message = "Order not accepted, seller does not have enough cards"
            elif self.state.player2cash[buyer_id] < price:
                message = "Order not accepted, buyer does not have enough cash"
            else:
                # Process the transaction
                self.state.player2cash[buyer_id] -= price
                self.state.player2cash[seller_id] += price
                self.state.player2cards[buyer_id][order.suit] += 1
                self.state.player2cards[seller_id][order.suit] -= 1
                self.state.player2card_count[buyer_id] += 1
                self.state.player2card_count[seller_id] -= 1
                message = "Order accepted"

                self.emit_event(
                    "transaction_processed",
                    {
                        "from": seller_id,
                        "to": buyer_id,
                        "suit": order.suit,
                        "amount": price,
                    },
                )

        if message == "Order accepted":
            # Reset the order book for this suit
            self.state.orderbook.bids[order.suit] = SampleRecord()
            self.state.orderbook.asks[order.suit] = SampleRecord()

        self.emit_event(
            "accept_order_processed",
            {"player_id": order.player_id, "message": message},
        )

        # Log the transaction for debugging
        logger.debug(
            f"Transaction: {message}. Current state: {self.state.model_dump()}"
        )

        return message

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

    def calculate_winner(self) -> Tuple[str, int]:
        max_score = -1
        winner = ""
        for player_id, cards in self.state.player2cards.items():
            score = (
                cards.get(self.state.goal_suit, 0) * 10
                + self.state.player2cash[player_id]
            )
            if score > max_score:
                max_score = score
                winner = player_id
        return winner, max_score

    async def pre_game_countdown(self):
        for i in range(3, 0, -1):
            await asyncio.sleep(1)
            await self.broadcast({"type": "message", "data": f"Game starting in {i}"})
        await self.start_game()

    async def countdown(self):
        while (
            self.state.countdown > 0
            and self.state.started
            and self.check_all_players_ready()
        ):
            await asyncio.sleep(self.update_interval)
            self.state.countdown -= 1
            state_to_broadcast = deepcopy(
                self.state.model_dump(exclude={"player2cards", "goal_suit"})
            )
            self.emit_event("game_state", state_to_broadcast)
        if self.state.started:
            await self.stop_game()

    async def stop_game(self):
        self.state.started = False
        self.state.countdown = self.timer_max
        if self.countdown_task:
            self.countdown_task.cancel()
            self.countdown_task = None

        winner, score = self.calculate_winner()

        end_game_stats = {
            "goal_suit": self.state.goal_suit,
            "winner": winner,
            "winner_score": score,
            "final_player_stats": {
                player_id: {
                    "cards": cards,
                    "cash": self.state.player2cash[player_id],
                    "score": cards.get(self.state.goal_suit, 0) * 10
                    + self.state.player2cash[player_id],
                }
                for player_id, cards in self.state.player2cards.items()
            },
        }

        self.emit_event("game_ended", end_game_stats)

    async def start_game(self):
        if not self.check_all_players_ready():
            return f"Not all players ready"

        await self.deal_cards()

        self.state.started = True
        self.state.countdown = self.timer_max
        self.emit_event("game_started", self.game_id)
        self.countdown_task = asyncio.create_task(self.countdown())
