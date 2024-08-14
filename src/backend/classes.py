from typing import Dict, List, Union

from pydantic import BaseModel


class Player(BaseModel):
    player_id: str
    ready: bool = False


sample_record: Dict[str, Union[int, str]] = {
    "price": -1,
    "player_id": "",
    "order_id": -1,
}


class OrderBook(BaseModel):

    bids: Dict[str, Dict[str, Union[int, str]]] = {
        "diamonds": sample_record,
        "hearts": sample_record,
        "clubs": sample_record,
        "spades": sample_record,
    }
    asks: Dict[str, Dict[str, Union[int, str]]] = {
        "diamonds": sample_record,
        "hearts": sample_record,
        "clubs": sample_record,
        "spades": sample_record,
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
    goal_suit: str = ""
    # currently building for only one round so no need to have pay to play
    # simply disribute the remaining cash to the players after adding the cash to the pot
    player2cash: Dict[str, int] = {}
    orderbook: OrderBook = OrderBook()
