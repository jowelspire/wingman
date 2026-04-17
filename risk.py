"""Risk controls for deterministic short-horizon trading."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class RiskConfig:
    max_bankroll_per_trade: float = 0.10
    daily_max_loss_pct: float = 0.20
    cooldown_after_loss_seconds: int = 180


@dataclass(slots=True)
class RiskState:
    bankroll: float
    day_start_bankroll: float
    realized_pnl: float = 0.0
    last_loss_ts: float | None = None
    open_events: set[str] = field(default_factory=set)
    trading_halted: bool = False


class RiskManager:
    def __init__(self, config: RiskConfig, initial_bankroll: float) -> None:
        self.config = config
        self.state = RiskState(
            bankroll=initial_bankroll,
            day_start_bankroll=initial_bankroll,
        )

    def can_open_trade(self, event_id: str, now: float | None = None) -> tuple[bool, str]:
        now = now or time.time()

        if self.state.trading_halted:
            return False, "Trading halted for day"

        if event_id in self.state.open_events:
            return False, "Existing open position on event"

        if self.state.last_loss_ts and now - self.state.last_loss_ts < self.config.cooldown_after_loss_seconds:
            return False, "Cooldown active after loss"

        max_loss_abs = self.config.daily_max_loss_pct * self.state.day_start_bankroll
        if -self.state.realized_pnl >= max_loss_abs:
            self.state.trading_halted = True
            return False, "Daily max loss reached"

        return True, "OK"

    def size_for_trade(self) -> float:
        return self.state.bankroll * self.config.max_bankroll_per_trade

    def register_open_trade(self, event_id: str) -> None:
        self.state.open_events.add(event_id)

    def register_close_trade(self, event_id: str, pnl: float, now: float | None = None) -> None:
        now = now or time.time()
        self.state.open_events.discard(event_id)
        self.state.realized_pnl += pnl
        self.state.bankroll += pnl

        if pnl < 0:
            self.state.last_loss_ts = now

        max_loss_abs = self.config.daily_max_loss_pct * self.state.day_start_bankroll
        if -self.state.realized_pnl >= max_loss_abs:
            self.state.trading_halted = True
