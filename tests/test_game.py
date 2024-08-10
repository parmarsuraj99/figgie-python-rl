import asyncio

import pytest

from src.backend.game import app, Game, Player, GameState, Constants


@pytest.fixture(scope="session")
def make_game():
    game = Game(game_id="test_game")
    return game


@pytest.fixture(scope="session")
def add_players():
    game = Game(game_id="test_game")
    player_1 = Player(player_id="player_1")
    player_2 = Player(player_id="player_2")
    player_3 = Player(player_id="player_3")
    player_4 = Player(player_id="player_4")
    player_5 = Player(player_id="player_5")
    game.add_player(player_1.player_id)
    game.add_player(player_2.player_id)
    game.add_player(player_3.player_id)
    game.add_player(player_4.player_id)
    game.add_player(player_5.player_id)
    return game


def test_game_initial_state(make_game):
    game = make_game
    assert game.state.started is False
    assert game.state.countdown == Constants.timer_countdown


def test_make_player():
    player_1 = Player(player_id="player_1")
    assert player_1.player_id == "player_1"
    assert player_1.ready is False


def test_add_player(make_game):
    game = make_game
    player_1 = Player(player_id="player_1")
    game.add_player(player_1.player_id)
    assert len(game.players) == 1
    assert "player_1" in game.players


def test_remove_player(make_game):
    game = make_game
    game.add_player("player_1")
    game.remove_player("player_1")
    assert len(game.players) == 0
    assert "player_1" not in game.players


def test_repeat_add_player(make_game):
    game = make_game
    game.add_player("player_1")
    assert game.add_player("player_1") == "Player player_1 already in game"


def test_player_is_ready(make_game):
    game = make_game
    game.add_player("player_1")
    game.player_is_ready("player_1")
    assert game.players["player_1"].ready is True


def test_all_players_ready(add_players):
    game = add_players
    game.player_is_ready("player_1")
    game.player_is_ready("player_2")
    game.player_is_ready("player_3")
    game.player_is_ready("player_4")
    game.player_is_ready("player_5")
    assert game.check_all_players_ready() is True


@pytest.mark.asyncio
async def test_start_stop_game(add_players):
    game = add_players
    asyncio.create_task(game.start_game())
    await asyncio.sleep(2)
    assert game.state.started is True
    assert game.state.countdown < Constants.timer_countdown

    await asyncio.sleep(Constants.timer_countdown)
    # assert the game is finally stopped
    assert game.state.started is False
    assert game.state.countdown == Constants.timer_countdown
