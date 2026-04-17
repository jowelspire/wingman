# Real-Time Sports Prediction Market Mean-Reversion Bot

This repository contains a **deterministic, rule-based** Python trading bot for sports prediction markets (Kalshi-style yes/no contracts).

## Strategy Goal

This bot is **not** trying to predict final game outcomes. It targets short-term market overreactions:

- Detect when a previously favored team experiences a sharp implied-probability drop.
- Enter a mean-reversion trade if game context still supports a rebound.
- Exit quickly via strict take-profit / stop-loss / time-based rules.

## Architecture

- `data_feed.py`
  - `GameState` model.
  - `MockSportsDataFeed` for simulation.
  - `ESPNDataFeed` scaffold with resilient polling + stale-data safeguards.
- `market.py`
  - `MarketTick`, `Order`, `Fill` models.
  - `MockMarket` simulated prediction market with scripted probability paths.
  - `LiveMarket` protocol wrapper for real API integration.
- `strategy.py`
  - Deterministic `MeanReversionStrategy` with shock-detection and strict exits.
- `execution.py`
  - `ExecutionEngine` with per-event locking and retry logic.
  - Position lifecycle + PnL utilities.
- `risk.py`
  - Position sizing, daily loss cutoffs, cooldown after loss, overlap prevention.
- `main.py`
  - Async orchestration across feeds, market, strategy, risk, and execution.
  - Simulation runner with built-in scenarios.
- `test_scenarios.py`
  - Example tests for entry/rebound/stop-loss behaviors.

## Safety Characteristics

- No LLM dependency for core decisions.
- Non-blocking async architecture (`asyncio`) to support low-latency loops.
- Explicit fail-safe behavior on feed failures/stale data.
- Strict loss controls and trading halt behavior after daily max loss.
- Designed for simulation-first validation before any live deployment.

## Run (Simulation)

```bash
python3 main.py --scenario entry_rebound --runtime 8
python3 main.py --scenario entry_stoploss --runtime 8
python3 main.py --scenario mixed --runtime 8
```

## Run Tests

```bash
python3 -m pytest -q
```

## Notes Before Any Live Use

1. Integrate authenticated, rate-limited production APIs in `ESPNDataFeed` and `LiveMarket`.
2. Add durable persistence (database/event log) for audit and recovery.
3. Backtest and paper-trade extensively before live capital.
4. Model slippage, fees, and partial fills realistically.
5. Add operational monitoring/alerts and circuit breakers.

## Important Disclaimer

This code does **not** guarantee profitability and should be treated as an educational/simulation framework. Real markets include execution risk, data issues, liquidity constraints, and regime shifts.
