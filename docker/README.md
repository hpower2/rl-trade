# Docker

Milestone 14 introduces the base container/runtime assets for the stack:

- `../compose.yaml`: Docker Compose stack for `postgres`, `redis`, `migrate`, `api`, `worker`, `training_worker`, `scheduler`, and `frontend`
- `compose.gpu.yaml`: optional GPU override for the dedicated `training_worker`
- `python.Dockerfile`: shared Python image used by the API, workers, scheduler, and migration job
- `frontend.Dockerfile`: Node/Vite image for the frontend preview runtime
- `scripts/startup_checks.py`: startup readiness checks for DB, Redis, MT5, and CUDA logging
- `scripts/start-python-service.sh`: tiny wrapper that runs startup checks before the target process

The build files now keep dependency downloads cacheable:

- `python.Dockerfile` installs runtime dependencies from `pyproject.toml` before copying the full source tree, then installs the local package with `--no-deps`, so normal code edits do not invalidate the heavy Python dependency layer.
- Both Dockerfiles use BuildKit cache mounts for package downloads (`/root/.cache/pip` and `/root/.npm`) so repeated builds reuse cached artifacts instead of downloading everything again.
- `make compose-build` forces `DOCKER_BUILDKIT=1` so those cache mounts are active in the standard local workflow.

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

Then verify that the expected Milestone 14 services actually reached their target runtime states:

```bash
make validate-compose-runtime
```

That command reads `docker compose ps --all --format json` and fails unless `postgres`, `redis`, `api`, and `frontend` are healthy, `worker`, `training_worker`, and `scheduler` are running, and `migrate` exited successfully.
It also waits through transient `starting` states during stack bring-up instead of requiring a manual pause before validation.

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
make validate-compose-gpu-host
make compose-build
TRAINING_WORKER_REQUIRE_CUDA=true docker compose -f compose.yaml -f docker/compose.gpu.yaml up -d
```

The GPU host preflight checks that the Docker engine advertises an `nvidia` runtime before you try to boot the GPU override stack. That fails fast on machines that can run the base Compose stack but are not prepared for GPU containers yet.

Then verify that the live `training_worker` actually reached the positive CUDA-ready path instead of only starting the container:

```bash
make validate-compose-gpu-runtime
```

That command reads the latest `training_worker` Compose logs and fails unless the most recent CUDA startup-check line reports `CUDA available with ...`. If you need to inspect a saved log export instead of the live container, run `python docker/scripts/verify_training_worker_gpu.py --log-file /path/to/training_worker.log`.
When used against a live stack, it will briefly retry while the `training_worker` is still starting and has not emitted its CUDA readiness line yet.

If no GPU is available, keep the base `compose.yaml` path. The `training_worker` will still start, log the degraded CUDA state, and stay CPU-only instead of blocking the rest of the stack.
