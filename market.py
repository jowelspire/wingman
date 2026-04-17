"""Prediction market interface and simulation."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import AsyncIterator

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class MarketTick:
    event_id: str
    team: str
    implied_prob: float  # 0.0-1.0
    bid: float
    ask: float
    timestamp: float


@dataclass(slots=True)
class Order:
    event_id: str
    team: str
    side: str  # BUY_YES / SELL_YES
    size_dollars: float
    max_price: float


@dataclass(slots=True)
class Fill:
    order: Order
    fill_price: float
    fill_time: float


class BaseMarket:
    async def stream_prices(self) -> AsyncIterator[MarketTick]:
        raise NotImplementedError

    async def place_order(self, order: Order) -> Fill:
        raise NotImplementedError


class MockMarket(BaseMarket):
    """Simulates a Kalshi-like yes-contract market with scripted shocks."""

    def __init__(
        self,
        event_id: str,
        team: str,
        tick_seconds: float = 0.2,
        scripted_probs: list[float] | None = None,
    ) -> None:
        self.event_id = event_id
        self.team = team
        self.tick_seconds = tick_seconds
        self.scripted_probs = scripted_probs or [
            0.67,
            0.66,
            0.65,
            0.48,
            0.49,
            0.53,
            0.56,
            0.58,
            0.60,
            0.62,
        ]
        self._idx = 0

    async def stream_prices(self) -> AsyncIterator[MarketTick]:
        while self._idx < len(self.scripted_probs):
            prob = self.scripted_probs[self._idx]
            self._idx += 1

            # Add spread + tiny noise to emulate microstructure.
            mid = max(0.01, min(0.99, prob + random.uniform(-0.002, 0.002)))
            spread = 0.01
            tick = MarketTick(
                event_id=self.event_id,
                team=self.team,
                implied_prob=mid,
                bid=max(0.0, mid - spread / 2),
                ask=min(1.0, mid + spread / 2),
                timestamp=time.time(),
            )
            LOGGER.debug("Market tick: %s", tick)
            yield tick
            await asyncio.sleep(self.tick_seconds)

    async def place_order(self, order: Order) -> Fill:
        await asyncio.sleep(0.01)
        slippage = random.uniform(0.0, 0.002)
        price = min(1.0, max(0.0, order.max_price + slippage))
        fill = Fill(order=order, fill_price=price, fill_time=time.time())
        LOGGER.info("Order filled: %s", fill)
        return fill


class MarketAPIClientProtocol:
    async def stream(self, event_id: str, team: str) -> AsyncIterator[MarketTick]:  # pragma: no cover
        raise NotImplementedError

    async def submit_order(self, order: Order) -> Fill:  # pragma: no cover
        raise NotImplementedError


class LiveMarket(BaseMarket):
    def __init__(self, client: MarketAPIClientProtocol, event_id: str, team: str) -> None:
        self.client = client
        self.event_id = event_id
        self.team = team

    async def stream_prices(self) -> AsyncIterator[MarketTick]:
        async for tick in self.client.stream(self.event_id, self.team):
            yield tick

    async def place_order(self, order: Order) -> Fill:
        return await self.client.submit_order(order)
