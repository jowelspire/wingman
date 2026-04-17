"""Example simulation tests for entry/rebound/stop-loss behavior."""

from __future__ import annotations

import asyncio

from main import build_simulation


async def run_and_collect(scenario: str, runtime: float = 6.0) -> float:
    bot = build_simulation(scenario)
    await bot.run(runtime_seconds=runtime)
    return bot.risk.state.realized_pnl


def test_probability_drop_then_rebound_exit_profit() -> None:
    pnl = asyncio.run(run_and_collect("entry_rebound"))
    assert pnl > 0, f"Expected positive pnl on rebound scenario, got {pnl}"


def test_probability_drop_then_stoploss_exit() -> None:
    pnl = asyncio.run(run_and_collect("entry_stoploss"))
    assert pnl < 0, f"Expected negative pnl on stoploss scenario, got {pnl}"


def test_probability_drop_entry_happens() -> None:
    bot = build_simulation("mixed")
    asyncio.run(bot.run(runtime_seconds=6.0))
    # At least one trade should have been attempted in mixed scenario.
    traded = bot.risk.state.realized_pnl != 0 or len(bot.risk.state.open_events) > 0
    assert traded, "Expected at least one trade to occur"
