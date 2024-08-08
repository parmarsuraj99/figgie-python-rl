import asyncio

import pytest

from src.backend.game import Game, Player


@pytest.fixture(scope="session")
def game():
    return Game(game_id="test_game")


def test_game_initialization(game):
    assert game.game_id == "test_game"
    assert not game.started
    assert game.countdown == 300
    assert game.players == []


def test_add_player(game):
    player = Player(player_id="player1")
    game.add_player(player)
    assert len(game.players) == 1
    assert game.players[0].player_id == "player1"


def test_remove_player(game):
    assert len(game.players) == 1
    game.remove_player("player1")
    assert len(game.players) == 0


def test_add_multiple_players(game):
    players = [Player(player_id=f"player{i}") for i in range(0, 4)]
    for player in players:
        game.add_player(player)
    assert len(game.players) == 4
    assert [p.player_id for p in game.players] == [
        "player0",
        "player1",
        "player2",
        "player3",
    ]


@pytest.mark.asyncio
async def test_start(game):
    start_task = asyncio.create_task(game.start())
    await asyncio.sleep(
        2
    )  # Wait for 2 seconds to allow the game to start and countdown to decrease
    print(game.countdown)

    assert game.started
    assert 0 <= game.countdown < 10
    await start_task

    try:
        await start_task
    except asyncio.CancelledError:
        print("Game task was cancelled as expected")

    assert not game.started
    assert (
        game.countdown == 10
    )  # Assuming the game resets countdown to 300 when stopped
