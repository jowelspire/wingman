"""Execution engine for fast entry/exit with guarded retries."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from market import BaseMarket, Fill, MarketTick, Order


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class Position:
    event_id: str
    team: str
    entry_price: float
    size_dollars: float
    entry_ts: float
    side: str = "BUY_YES"

    def unrealized_return(self, current_prob: float) -> float:
        # Simplified mark-to-market based on probability/contract price.
        if self.entry_price <= 0:
            return 0.0
        return (current_prob - self.entry_price) / self.entry_price


class ExecutionEngine:
    def __init__(self, market: BaseMarket, max_retries: int = 2) -> None:
        self.market = market
        self.max_retries = max_retries
        self._locks: dict[str, asyncio.Lock] = {}

    def _event_lock(self, event_id: str) -> asyncio.Lock:
        if event_id not in self._locks:
            self._locks[event_id] = asyncio.Lock()
        return self._locks[event_id]

    async def open_position(self, tick: MarketTick, size_dollars: float) -> Position:
        order = Order(
            event_id=tick.event_id,
            team=tick.team,
            side="BUY_YES",
            size_dollars=size_dollars,
            max_price=tick.ask,
        )
        fill = await self._submit_with_retry(order)
        return Position(
            event_id=tick.event_id,
            team=tick.team,
            entry_price=fill.fill_price,
            size_dollars=size_dollars,
            entry_ts=fill.fill_time,
        )

    async def close_position(self, position: Position, tick: MarketTick) -> Fill:
        order = Order(
            event_id=position.event_id,
            team=position.team,
            side="SELL_YES",
            size_dollars=position.size_dollars,
            max_price=tick.bid,
        )
        return await self._submit_with_retry(order)

    async def _submit_with_retry(self, order: Order) -> Fill:
        lock = self._event_lock(order.event_id)
        async with lock:
            last_exc: Exception | None = None
            for attempt in range(1, self.max_retries + 2):
                try:
                    return await self.market.place_order(order)
                except Exception as exc:
                    last_exc = exc
                    LOGGER.warning(
                        "Order submit failed (attempt %d/%d) for %s: %s",
                        attempt,
                        self.max_retries + 1,
                        order,
                        exc,
                    )
                    await asyncio.sleep(min(0.05 * attempt, 0.25))
            raise RuntimeError(f"Order failed after retries: {order}") from last_exc


def realized_pnl(position: Position, exit_fill: Fill) -> float:
    # Contracts are normalized to [0,1] price. PnL in dollar terms:
    # size * ((exit-entry)/entry)
    if position.entry_price <= 0:
        return 0.0
    pct = (exit_fill.fill_price - position.entry_price) / position.entry_price
    return position.size_dollars * pct


def hold_seconds(position: Position) -> float:
    return max(0.0, time.time() - position.entry_ts)
