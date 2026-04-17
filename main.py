"""Entry point and simulation harness for the sports market bot."""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from data_feed import BaseSportsDataFeed, GameState, MockSportsDataFeed
from execution import ExecutionEngine, Position, realized_pnl
from market import BaseMarket, MarketTick, MockMarket
from risk import RiskConfig, RiskManager
from strategy import MeanReversionStrategy, StrategyConfig


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("bot")


@dataclass(slots=True)
class BotConfig:
    event_id: str = "NBA-123"
    team: str = "TEAM_A"


class TradingBot:
    def __init__(
        self,
        config: BotConfig,
        data_feed: BaseSportsDataFeed,
        market: BaseMarket,
        strategy: MeanReversionStrategy,
        execution: ExecutionEngine,
        risk: RiskManager,
    ) -> None:
        self.config = config
        self.data_feed = data_feed
        self.market = market
        self.strategy = strategy
        self.execution = execution
        self.risk = risk

        self.latest_game: Optional[GameState] = None
        self.latest_tick: Optional[MarketTick] = None
        self.position: Optional[Position] = None
        self._stop = asyncio.Event()

    async def run(self, runtime_seconds: float = 20.0) -> None:
        tasks = [
            asyncio.create_task(self._consume_game()),
            asyncio.create_task(self._consume_market()),
            asyncio.create_task(self._decision_loop()),
            asyncio.create_task(self._stop_after(runtime_seconds)),
        ]
        try:
            await self._stop.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _consume_game(self) -> None:
        async for game in self.data_feed.stream():
            self.latest_game = game

    async def _consume_market(self) -> None:
        async for tick in self.market.stream_prices():
            self.latest_tick = tick
            self.strategy.on_market_tick(tick)

    async def _decision_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(0.05)
            if self.latest_tick is None:
                continue

            if self.position is None:
                decision = self.strategy.maybe_enter(self.latest_game, self.latest_tick, has_position=False)
                if decision.action != "ENTER":
                    LOGGER.debug("No entry: %s", decision.reason)
                    continue

                allowed, reason = self.risk.can_open_trade(self.config.event_id)
                if not allowed:
                    LOGGER.info("Risk blocked entry: %s", reason)
                    continue

                size = self.risk.size_for_trade()
                self.position = await self.execution.open_position(self.latest_tick, size)
                self.risk.register_open_trade(self.config.event_id)
                LOGGER.info("ENTERED: %s | reason=%s", self.position, decision.reason)
            else:
                decision = self.strategy.maybe_exit(self.position, self.latest_tick)
                if decision.action != "EXIT":
                    continue

                fill = await self.execution.close_position(self.position, self.latest_tick)
                pnl = realized_pnl(self.position, fill)
                self.risk.register_close_trade(self.config.event_id, pnl)
                LOGGER.info(
                    "EXITED: fill=%.4f pnl=$%.2f reason=%s bankroll=$%.2f realized=$%.2f",
                    fill.fill_price,
                    pnl,
                    decision.reason,
                    self.risk.state.bankroll,
                    self.risk.state.realized_pnl,
                )
                self.position = None

    async def _stop_after(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
        self._stop.set()


def build_simulation(scenario: str) -> TradingBot:
    config = BotConfig()
    data_feed = MockSportsDataFeed(event_id=config.event_id, favored_team=config.team, tick_seconds=0.2)

    # Scenarios requested by user:
    if scenario == "entry_rebound":
        probs = [0.70, 0.69, 0.67, 0.50, 0.51, 0.54, 0.57, 0.60]
    elif scenario == "entry_stoploss":
        probs = [0.72, 0.70, 0.68, 0.52, 0.50, 0.48, 0.46, 0.44]
    else:  # generic mixed
        probs = [0.68, 0.67, 0.65, 0.49, 0.50, 0.53, 0.51, 0.48, 0.55]

    market = MockMarket(event_id=config.event_id, team=config.team, tick_seconds=0.2, scripted_probs=probs)

    strategy = MeanReversionStrategy(
        StrategyConfig(
            favored_threshold=0.60,
            shock_drop_abs=0.15,
            shock_window_seconds=120,
            take_profit_pct=0.03,
            stop_loss_pct=-0.05,
            max_hold_seconds=120,
        )
    )
    execution = ExecutionEngine(market)
    risk = RiskManager(
        RiskConfig(
            max_bankroll_per_trade=0.10,
            daily_max_loss_pct=0.20,
            cooldown_after_loss_seconds=120,
        ),
        initial_bankroll=1000.0,
    )

    return TradingBot(config, data_feed, market, strategy, execution, risk)


async def run_cli(scenario: str, runtime: float) -> None:
    bot = build_simulation(scenario)
    await bot.run(runtime_seconds=runtime)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real-time sports prediction market bot")
    p.add_argument(
        "--scenario",
        default="entry_rebound",
        choices=["entry_rebound", "entry_stoploss", "mixed"],
        help="Simulation scenario",
    )
    p.add_argument("--runtime", type=float, default=8.0, help="Run time in seconds")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_cli(args.scenario, args.runtime))
