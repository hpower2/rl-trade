# AGENTS.md

## Project
Forex Trainer & Paper Trading Dashboard

## Core stack
- Backend: Python 3.12 + FastAPI
- Workers: Celery + Redis
- Frontend: React + TypeScript + Vite
- Database: PostgreSQL + TimescaleDB
- ML: PyTorch, Gymnasium, Stable-Baselines3
- Broker integration: MetaTrader5 Python package
- Containers: Docker Compose
- Training workers may use NVIDIA GPU

## Non-negotiable rules
- Demo trading only. Never allow live trading.
- Enforce trading restrictions in backend code, not just frontend.
- Do not run long-running jobs in API request handlers.
- Keep API responsive; use background workers for ingestion, preprocessing, training, evaluation, and trading loops.
- A symbol cannot be traded unless it has an approved trained model.
- Approval requires at least:
  - confidence >= 70%
  - risk-to-reward >= 2.0
- Candlestick pattern features must be part of preprocessing and model inputs.
- Prefer maintainable architecture over shortcuts.
- Keep modules small and separated by responsibility.

## Architecture expectations
- Separate API, workers, training, and frontend concerns cleanly.
- Keep CPU-bound and GPU-bound workloads isolated.
- Use TimescaleDB hypertables for OHLC candle storage.
- Normalize all market timestamps to UTC.
- Use WebSockets for live dashboard updates.

## Coding expectations
- Return file paths for every created or modified file.
- Create runnable code, not toy pseudocode.
- Use strong typing where practical.
- Add tests for critical business rules.
- Add clear logging for jobs, training, and trade execution.
- Use environment variables for secrets and configuration.

## Safety expectations
- Block live accounts explicitly in MT5 integration.
- Add audit logging for model approval and paper trade execution.
- Fail safely when market data, MT5, Redis, DB, or GPU is unavailable.

## Workflow
For large features:
1. summarize architecture briefly
2. scaffold folder structure
3. build backend foundation
4. build DB models and migrations
5. build workers and tasks
6. build training/evaluation pipeline
7. build frontend pages
8. wire Docker and docs