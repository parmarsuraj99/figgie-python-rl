from typing import Dict, List, Union

from pydantic import BaseModel


class Constants:
    timer_countdown = 10
    suits: List[str] = ["hearts", "diamonds", "clubs", "spades"]
    suit2colors: Dict[str, str] = {
        "hearts": "red",
        "diamonds": "red",
        "clubs": "black",
        "spades": "black",
    }
    color2suits: Dict[str, List[str]] = {
        "red": ["hearts", "diamonds"],
        "black": ["clubs", "spades"],
    }
    suit_counts: List[int] = [8, 10, 10, 12]
    goal_suit_counts: List[int] = [8, 10]
    cash_per_player = 400
    cash_to_enter = 50


class Player(BaseModel):
    player_id: str
    ready: bool = False


class SampleRecord(BaseModel):
    price: int = -1
    player_id: str = ""
    order_id: int = -1


class OrderBook(BaseModel):

    bids: Dict[str, SampleRecord] = {
        "diamonds": SampleRecord(),
        "hearts": SampleRecord(),
        "clubs": SampleRecord(),
        "spades": SampleRecord(),
    }
    asks: Dict[str, SampleRecord] = {
        "diamonds": SampleRecord(),
        "hearts": SampleRecord(),
        "clubs": SampleRecord(),
        "spades": SampleRecord(),
    }


class Order(BaseModel):
    is_bid: Union[bool, None] = None
    suit: str = ""
    price: int = -1
    player_id: str = ""


class GameState(BaseModel):
    started: bool = False
    countdown: int = Constants.timer_countdown
    player2cards: Dict[str, Dict[str, int]] = {}
    player2card_count: Dict[str, int] = {}
    goal_suit: str = ""
    # currently building for only one round so no need to have pay to play
    # simply disribute the remaining cash to the players after adding the cash to the pot
    player2cash: Dict[str, int] = {}
    orderbook: OrderBook = OrderBook()
