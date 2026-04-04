# Docker

Milestone 14 introduces the base container/runtime assets for the stack:

- `../compose.yaml`: Docker Compose stack for `postgres`, `redis`, `migrate`, `api`, `worker`, `training_worker`, `scheduler`, and `frontend`
- `compose.gpu.yaml`: optional GPU override for the dedicated `training_worker`
- `python.Dockerfile`: shared Python image used by the API, workers, scheduler, and migration job
- `frontend.Dockerfile`: Node/Vite image for the frontend preview runtime
- `scripts/startup_checks.py`: startup readiness checks for DB, Redis, MT5, and CUDA logging
- `scripts/start-python-service.sh`: tiny wrapper that runs startup checks before the target process

Validate the current Compose slice with:

```bash
docker compose config
```

Validate the GPU override layer too:

```bash
docker compose -f compose.yaml -f docker/compose.gpu.yaml config
```

Build the shared runtime images once:

```bash
make compose-build
```

Boot the stack with the default published ports:

```bash
make compose-up
```

The default stack now isolates CPU and GPU-adjacent workloads:

- `worker`: ingestion, preprocessing, evaluation, trading, and maintenance queues
- `training_worker`: supervised and RL training queues

That keeps the general worker lane runnable on non-GPU hosts while giving the training lane its own CUDA policy and queue ownership.

If your machine already uses `5432`, `6379`, `8000`, or `4173`, override the host-published ports without changing the in-container service ports:

```bash
POSTGRES_HOST_PORT=55432 \
REDIS_HOST_PORT=56379 \
API_HOST_PORT=58000 \
FRONTEND_HOST_PORT=54173 \
docker compose up -d
```

When you use alternate host ports, update any host-side clients accordingly. For example, a local backend process should point `DATABASE_URL` at `localhost:${POSTGRES_HOST_PORT}` and `REDIS_URL` at `localhost:${REDIS_HOST_PORT}`.

The Compose file intentionally reuses the prebuilt `rl-trade-python:local` image across `migrate`, `api`, `worker`, and `scheduler`. That keeps local validation from unpacking four duplicate copies of the same dependency-heavy image during `docker compose up`.

To request a GPU for the dedicated training worker on hosts with NVIDIA container support, build first and then layer in the override file:

```bash
make compose-build
TRAINING_WORKER_REQUIRE_CUDA=true docker compose -f compose.yaml -f docker/compose.gpu.yaml up -d
```

If no GPU is available, keep the base `compose.yaml` path. The `training_worker` will still start, log the degraded CUDA state, and stay CPU-only instead of blocking the rest of the stack.
