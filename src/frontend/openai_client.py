import os
import json
import asyncio
import websockets
import openai
from dotenv import load_dotenv
from collections import deque
from client_dev import GameClient, log_to_file


class OpenAILLMAgent(GameClient):
    def __init__(self, player_id, uri):
        super().__init__(player_id, uri)
        self.cash = 400
        self.inventory = {suit: 0 for suit in ["hearts", "diamonds", "clubs", "spades"]}
        self.recent_updates = deque(maxlen=5)

        # Load OpenAI API key from .env file
        load_dotenv()
        openai.api_key = os.getenv("OPENAI_API_KEY")

        self.system_prompt = """
        You are an AI agent playing a card trading game called Figgie. Your goal is to maximize your profit by trading cards and predicting the goal suit. Here are the rules:

        1. There are four suits: hearts, diamonds, clubs, and spades.
        2. One suit is secretly chosen as the goal suit, worth 10 points each at the end.
        3. You start with 400 cash and a random distribution of cards.
        4. You can buy and sell cards by placing or accepting orders.
        5. The game ends after a set time, and the player with the highest score (goal cards * 10 + cash) wins.

        Your task is to analyze the game state, recent updates, and make strategic decisions to maximize your score. Consider the following:

        - Predict the likely goal suit based on trading patterns and card distributions.
        - Balance your inventory to have more of the predicted goal suit.
        - Place strategic bids and asks to profit from price differences.
        - Manage your cash to ensure you can make important trades.

        Provide your decision as a JSON-formatted string with the following structure:
        {
            "action": "place_order" or "accept_order",
            "suit": "hearts" or "diamonds" or "clubs" or "spades",
            "price": integer,
            "is_bid": true or false
        }

        If you decide not to take any action, return:
        {
            "action": "wait"
        }
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
        """

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )

            decision = response.choices[0].message.content.strip()
            log_to_file(self.player_id, f"LLM Decision: {decision}")

            # Parse the decision and take action
            import json

            decision_dict = json.loads(decision)

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

    async def update_inventory(self, suit, is_buy, price):
        if is_buy:
            self.inventory[suit] += 1
            self.cash -= price
        else:
            self.inventory[suit] -= 1
            self.cash += price

    async def receive_messages(self):
        try:
            while True:
                response = await asyncio.wait_for(self.websocket.recv(), timeout=30)
                response_data = json.loads(response)
                log_to_file(self.player_id, f"Received: {response_data}")

                # Add the update to recent_updates
                self.recent_updates.append(response_data)

                if response_data["type"] == "game_state":
                    self.game_state = response_data["data"]
                    await self.make_decision()

                # ... (rest of the receive_messages method remains the same)

        except asyncio.TimeoutError:
            log_to_file(
                self.player_id, "No message received for 30 seconds, closing connection"
            )
        except websockets.exceptions.ConnectionClosed:
            log_to_file(self.player_id, "Connection closed")
        finally:
            await self.websocket.close()
            log_to_file(self.player_id, "Disconnected")
