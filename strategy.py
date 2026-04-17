"""Deterministic mean-reversion strategy engine."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

from data_feed import GameState
from execution import Position, hold_seconds
from market import MarketTick

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class StrategyConfig:
    favored_threshold: float = 0.60
    shock_drop_abs: float = 0.15
    shock_window_seconds: float = 60.0
    take_profit_pct: float = 0.05
    stop_loss_pct: float = -0.05
    max_hold_seconds: float = 180.0
    min_seconds_remaining: int = 90
    max_feed_delay_ms: int = 2000


@dataclass(slots=True)
class StrategyDecision:
    action: str  # ENTER / EXIT / HOLD / SKIP
    reason: str


class MeanReversionStrategy:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.history: Deque[MarketTick] = deque(maxlen=300)

    def on_market_tick(self, tick: MarketTick) -> None:
        self.history.append(tick)

    def maybe_enter(self, game: Optional[GameState], latest_tick: MarketTick, has_position: bool) -> StrategyDecision:
        if has_position:
            return StrategyDecision("HOLD", "Already in position")

        if game is None:
            return StrategyDecision("SKIP", "No game state available")

        if game.feed_delay_ms > self.config.max_feed_delay_ms:
            return StrategyDecision("SKIP", "Game feed stale")

        if game.seconds_remaining < self.config.min_seconds_remaining:
            return StrategyDecision("SKIP", "Too close to end of game")

        if game.injury_flag:
            return StrategyDecision("SKIP", "Potential structural game change (injury)")

        if game.score_diff_for_favorite < -12:
            return StrategyDecision("SKIP", "Structural collapse risk: favorite down too much")

        drop = self._recent_drop(latest_tick)
        if drop is None:
            return StrategyDecision("SKIP", "Insufficient history")

        prior_prob, current_prob = drop
        if prior_prob < self.config.favored_threshold:
            return StrategyDecision("SKIP", "Team was not sufficiently favored")

        abs_drop = prior_prob - current_prob
        if abs_drop < self.config.shock_drop_abs:
            return StrategyDecision("SKIP", f"Drop too small ({abs_drop:.3f})")

        return StrategyDecision("ENTER", f"Shock detected: {prior_prob:.3f} -> {current_prob:.3f}")

    def maybe_exit(self, position: Position, latest_tick: MarketTick) -> StrategyDecision:
        r = position.unrealized_return(latest_tick.implied_prob)
        if r >= self.config.take_profit_pct:
            return StrategyDecision("EXIT", f"Take profit hit ({r:.2%})")

        if r <= self.config.stop_loss_pct:
            return StrategyDecision("EXIT", f"Stop loss hit ({r:.2%})")

        if hold_seconds(position) >= self.config.max_hold_seconds:
            return StrategyDecision("EXIT", "Time-based exit")

        return StrategyDecision("HOLD", f"Position open ({r:.2%})")

    def _recent_drop(self, latest_tick: MarketTick) -> tuple[float, float] | None:
        now = latest_tick.timestamp
        valid = [t for t in self.history if now - t.timestamp <= self.config.shock_window_seconds]
        if len(valid) < 2:
            return None
        max_prob = max(t.implied_prob for t in valid)
        return max_prob, latest_tick.implied_prob
