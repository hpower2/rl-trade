# Architecture Notes

## Service boundaries

- The API owns request/response orchestration, validation, and operator-facing control planes.
- Workers own long-running ingestion, preprocessing, training, evaluation, and paper-trading loops.
- Shared Python libraries keep settings, safety controls, and future domain logic consistent between services.
- The frontend remains isolated in `apps/frontend` and talks to the API/WebSocket surface rather than importing backend code.

## Milestone 1 decisions

- One editable Python install at the repo root keeps early imports simple while still preserving app/lib boundaries.
- Shared settings live in `libs/common` and reject any attempt to disable paper-only safeguards through environment variables.
- Celery is bootstrapped early so later queue work can extend existing modules rather than replacing the scaffold.
- The frontend uses an npm workspace so more apps or shared UI packages can be added without reshaping the repo.
