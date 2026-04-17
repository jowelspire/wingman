"""Live and simulated sports data feed abstractions."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import AsyncIterator, Optional


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GameState:
    event_id: str
    timestamp: float
    home_team: str
    away_team: str
    favored_team: str
    score_home: int
    score_away: int
    period: int
    seconds_remaining: int
    possession: Optional[str]
    injury_flag: bool = False
    feed_delay_ms: int = 0

    @property
    def score_diff_for_favorite(self) -> int:
        if self.favored_team == self.home_team:
            return self.score_home - self.score_away
        return self.score_away - self.score_home


class BaseSportsDataFeed:
    """Abstract sports feed. Subclasses must yield `GameState` objects."""

    async def stream(self) -> AsyncIterator[GameState]:
        raise NotImplementedError


class MockSportsDataFeed(BaseSportsDataFeed):
    """Deterministic-ish game state stream for simulation/testing."""

    def __init__(self, event_id: str, favored_team: str, tick_seconds: float = 0.2) -> None:
        self.event_id = event_id
        self.favored_team = favored_team
        self.tick_seconds = tick_seconds
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    async def stream(self) -> AsyncIterator[GameState]:
        home = "TEAM_A"
        away = "TEAM_B"
        period = 4
        seconds_remaining = 12 * 60
        score_home, score_away = 71, 66

        while seconds_remaining > 0 and not self._stopped:
            # Mild random walk to keep state realistic without changing strategy determinism.
            if random.random() < 0.18:
                if random.random() < 0.52:
                    score_home += random.choice([1, 2, 3])
                else:
                    score_away += random.choice([1, 2, 3])

            seconds_remaining -= 4
            possession = random.choice([home, away, None])
            injury = random.random() < 0.005
            delay_ms = random.choice([0, 0, 0, 150, 300])

            state = GameState(
                event_id=self.event_id,
                timestamp=time.time(),
                home_team=home,
                away_team=away,
                favored_team=self.favored_team,
                score_home=score_home,
                score_away=score_away,
                period=period,
                seconds_remaining=max(seconds_remaining, 0),
                possession=possession,
                injury_flag=injury,
                feed_delay_ms=delay_ms,
            )
            LOGGER.debug("Game state tick: %s", state)
            yield state
            await asyncio.sleep(self.tick_seconds)


class ESPNDataFeed(BaseSportsDataFeed):
    """Placeholder adapter for a real ESPN-like API client.

    This class demonstrates robust polling behavior and fail-safe handling,
    but leaves endpoint details injectable so no fragile hardcoding is required.
    """

    def __init__(
        self,
        client: "ESPNClientProtocol",
        event_id: str,
        poll_interval: float = 0.5,
        max_stale_seconds: float = 5.0,
    ) -> None:
        self.client = client
        self.event_id = event_id
        self.poll_interval = poll_interval
        self.max_stale_seconds = max_stale_seconds
        self._last_state_ts: float | None = None

    async def stream(self) -> AsyncIterator[GameState]:
        while True:
            try:
                state = await self.client.fetch_game_state(self.event_id)
                self._last_state_ts = time.time()
                yield state
            except Exception as exc:  # broad by design to keep the bot alive
                LOGGER.exception("Sports feed fetch error for %s: %s", self.event_id, exc)
                now = time.time()
                if self._last_state_ts and now - self._last_state_ts > self.max_stale_seconds:
                    LOGGER.warning(
                        "Feed stale for %.2fs (limit %.2fs) - strategy should avoid new entries",
                        now - self._last_state_ts,
                        self.max_stale_seconds,
                    )
            await asyncio.sleep(self.poll_interval)


class ESPNClientProtocol:
    async def fetch_game_state(self, event_id: str) -> GameState:  # pragma: no cover - interface only
        raise NotImplementedError
