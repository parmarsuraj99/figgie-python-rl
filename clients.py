import asyncio
import concurrent.futures
import json
import os
import random
from collections import deque
from datetime import datetime
from typing import Dict, List, Literal, Optional, Union

import openai
import websockets
from dotenv import load_dotenv

from src.clients.agents import (
    AggressiveTrader,
    GameClient,
    MarketMaker,
    SpeculativeAccumulator,
)
from src.clients.llm_agents import LLMAgent


class AgentPool:
    def __init__(self, agent_class, num_workers, *args, **kwargs):
        self.agent_class = agent_class
        self.num_workers = num_workers
        self.args = args
        self.kwargs = kwargs
        self.agents = []

    async def start(self):
        for i in range(self.num_workers):
            agent = self.agent_class(*self.args, **self.kwargs)
            self.agents.append(agent)
            await agent.connect()

    async def run(self):
        tasks = [agent.receive_messages() for agent in self.agents]
        await asyncio.gather(*tasks)


async def main():
    base_uri = f"ws://localhost:8000/ws"
    agent_pools = [
        AgentPool(AggressiveTrader, 1, "aggressive_trader", f"{base_uri}"),
        AgentPool(SpeculativeAccumulator, 1, "speculative_accumulator", f"{base_uri}"),
        # AgentPool(SpeculativeAccumulator, 1, "speculative_accumulator2", f"{base_uri}"),
        # AgentPool(SpeculativeAccumulator, 1, "speculative_accumulator3", f"{base_uri}"),
        AgentPool(
            LLMAgent,
            1,
            "openai_champion",
            f"{base_uri}",
            instructions="Guess the goal suit and place smart orders to maximize profit and win the game with most profit",
            llm_provider="openai",
        ),
        AgentPool(
            LLMAgent,
            1,
            "openai_mm",
            f"{base_uri}",
            instructions="Guess goal suit and place smart orders to act as a market maker, be aggressive",
            llm_provider="openai",  # Change to "anthropic" for Anthropic
        ),
    ]

    await asyncio.gather(*(pool.start() for pool in agent_pools))
    await asyncio.sleep(2)

    # Send ready signal for all agents
    await asyncio.gather(
        *(agent.send_ready() for pool in agent_pools for agent in pool.agents)
    )

    # Run all agent pools
    await asyncio.gather(*(pool.run() for pool in agent_pools))


if __name__ == "__main__":

    # Load environment variables
    load_dotenv()

    # Clear logs directory
    os.system("rm -rf player_logs")

    # Run...
    asyncio.run(main())
