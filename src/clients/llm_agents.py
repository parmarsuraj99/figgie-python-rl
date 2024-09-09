import asyncio
import json
import os
import random
from collections import deque
from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

import anthropic
import openai
import websockets
from dotenv import load_dotenv
from pydantic import BaseModel

from src.clients.agents import GameClient, log_to_file


class Order(BaseModel):
    action: Literal["place_order", "accept_order", "wait"]
    suit: Literal["hearts", "diamonds", "clubs", "spades"]
    price: int
    is_bid: bool


class Orders(BaseModel):
    orders: List[Order]


def parse_decision(decision: str) -> str:
    """parse the decision from the LLM API response"""
    decision = decision.split("```json")[1].split("```")[0]
    return decision


class LLMAgent(GameClient):
    def __init__(self, player_id, uri, instructions: str, llm_provider: str = "openai"):
        super().__init__(player_id, uri)
        self.cash = 400
        self.inventory = {suit: 0 for suit in ["hearts", "diamonds", "clubs", "spades"]}
        self.recent_updates = deque(maxlen=30)
        self.instructions = instructions
        self.llm_provider = llm_provider

        if self.llm_provider == "openai":
            self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif self.llm_provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            raise ValueError("Unsupported LLM provider")

        self.system_prompt = f"""
        You are an AI agent playing a card trading game called Figgie. Your goal is to maximize your profit by trading cards and predicting the goal suit. Here are the rules:

        1. There are four suits: hearts, diamonds, clubs, and spades.
        2. One suit is secretly chosen as the goal suit, worth 10 points each at the end.
        3. The goal suit is of the same color as the suit with the most cards in the deck.
        4. You start with 400 cash and a random distribution of cards. 50 cash is required to enter the game.
        5. You can buy and sell cards by placing or accepting orders.
        6. The game ends after a set time, and the player with the highest score (goal cards * 10 + cash) wins.

        Your task is to {self.instructions}. You can place orders, accept orders, or wait for more information before making a decision. Good luck!
        """

    async def make_decision(self):
        if "orderbook" not in self.game_state:
            return

        # Prepare the prompt with the current game state and recent updates
        prompt = f"""
        Current game state:
        {self.game_state}

        Your inventory:
        {self.inventory}

        Your cash:
        {self.cash}

        Recent updates:
        {list(self.recent_updates)}

        Based on this information, what action would you like to take? Respond with a JSON-formatted decision.
        in this format {Order.model_json_schema()}. please directyly respond with json
        """

        try:
            if self.llm_provider == "openai":
                response = self.client.beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    response_format=Order,
                )
                decision = response.choices[0].message.parsed.model_dump_json()
                log_to_file(self.player_id, f"OpenAI response: {decision}")
            elif self.llm_provider == "anthropic":
                response = self.client.beta.prompt_caching.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=1024,
                    system=[
                        {
                            "type": "text",
                            "text": self.system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": prompt}],
                    extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
                )
                decision = response.content[0].text

            decision_dict = json.loads(decision)
            decision_dict["player_id"] = self.player_id

            if decision_dict["action"] == "place_order":
                await self.place_order(
                    decision_dict["suit"],
                    decision_dict["price"],
                    decision_dict["is_bid"],
                )
            elif decision_dict["action"] == "accept_order":
                await self.accept_order(decision_dict["suit"], decision_dict["is_bid"])
            # If action is "wait", do nothing

        except Exception as e:
            log_to_file(self.player_id, f"Error in make_decision: {str(e)}")

    async def receive_messages(self):
        try:
            while True:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=30)
                    response_data = json.loads(response)
                    log_to_file(self.player_id, f"Received: {response_data}")

                    # Add the update to recent_updates
                    self.recent_updates.append(response_data)

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

        except asyncio.TimeoutError:
            log_to_file(
                self.player_id, "No message received for 30 seconds, closing connection"
            )
        except websockets.exceptions.ConnectionClosed:
            log_to_file(self.player_id, "Connection closed")
        finally:
            await self.websocket.close()
            log_to_file(self.player_id, "Disconnected")
