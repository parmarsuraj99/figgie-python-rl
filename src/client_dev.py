import asyncio
import json
import os
import random
from collections import deque
from datetime import datetime
from typing import Dict, List, Union, Literal, Optional

import openai
import websockets
from dotenv import load_dotenv

from clients.agents import GameClient, log_to_file
from clients.agents import AggressiveTrader, SpeculativeAccumulator, MarketMaker
from clients.llm_agents import LLMAgent

import concurrent.futures


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
        # AgentPool(MarketMaker, 1, "market_maker", f"{base_uri}"),
        AgentPool(
            LLMAgent,
            1,
            "openai_champion",
            f"{base_uri}",
            instructions="Guess and place smart orders to maximize profit and win the game",
            llm_provider="openai",
        ),
        AgentPool(
            LLMAgent,
            1,
            "claude_mm",
            f"{base_uri}",
            instructions="Guess and place smart orders to act as a market maker",
            llm_provider="anthropic",
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
    # Clear logs directory
    os.system("rm -rf player_logs")

    # Run...
    asyncio.run(main())
