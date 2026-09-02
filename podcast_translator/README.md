# PodFlow MVP

PodFlow is a podcast translation MVP focused on one end-to-end path:

1. SMS login
2. Local audio upload
3. Task creation
4. Async worker processing
5. Task detail realtime progress
6. Result playback and download

The repository now defaults to a mock pipeline for local acceptance and CI. The real AI pipeline is available as an opt-in runtime mode.

For product overview, prerequisites, and end-user usage, see the root [README.md](../README.md). This document focuses on developer/operator details: environment variables, real-pipeline notes, and server deployment.

## Local MVP Run

The default single-machine setup runs the mock pipeline and is intended to work without GPU dependencies.

```bash
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080).

Service ports:

- `8080`: unified user entry via Nginx
- `8000`: backend API
- `9000`: MinIO S3 API
- `9001`: MinIO console
- `5432`: main Postgres
- `6379`: Redis

## Default Runtime Mode

`docker-compose.yml` defaults to:

- `PCT_PIPELINE_MODE=mock`
- `PCT_SMS_PROVIDER=mock`
- dummy OpenAI credentials for configuration completeness

That means the main chain is demoable out of the box:

1. Request SMS code
2. Log in
3. Upload a local audio file
4. Watch progress move across pipeline stages
5. Play or download the generated result

## Environment Variables

Use `.env.example` as the starting point for local overrides.
Use `frontend/.env.example` as the starting point for frontend-side API overrides.

Important variables:

- `PCT_SECRET_KEY`
- `PCT_DATABASE_URL`
- `PCT_REDIS_URL`
- `PCT_S3_ENDPOINT`
- `PCT_S3_PUBLIC_ENDPOINT`
- `PCT_S3_BUCKET`
- `PCT_S3_ACCESS_KEY`
- `PCT_S3_SECRET_KEY`
- `PCT_CREDENTIALS_ENCRYPTION_KEY`
- `PCT_DEEPSEEK_API_KEY`
- `PCT_OPENAI_API_KEY`
- `PCT_HF_TOKEN`
- `PCT_DASHSCOPE_API_KEY`
- `PCT_ELEVENLABS_API_KEY`
- `PCT_VOICE_CLONE_PROVIDER` — `elevenlabs` | `voxcpm` | `cosyvoice`
- `PCT_VOXCPM_MODEL` / `PCT_VOXCPM_DEVICE` — only when using the self-hosted VoxCPM engine
- `PCT_SMS_PROVIDER`
- `PCT_PIPELINE_MODE`
- `PCT_MOCK_PIPELINE_STAGE_DELAY_SECONDS`

Provider API keys (`PCT_DEEPSEEK_API_KEY`, `PCT_HF_TOKEN`, `PCT_ELEVENLABS_API_KEY`, `PCT_DASHSCOPE_API_KEY`) are **optional** as env vars: they act as a system-wide fallback. Each user can instead enter keys in **Profile → API management** (encrypted, per-user). Resolution order is **user (DB) keys first, then env fallback**. Non-key runtime config (`PCT_PIPELINE_MODE`, `PCT_SECRET_KEY`, `PCT_CREDENTIALS_ENCRYPTION_KEY`, endpoints, etc.) must still be set in env.

`PCT_S3_ENDPOINT` is for backend and worker access to object storage. `PCT_S3_PUBLIC_ENDPOINT` is the browser-facing host used when generating playback/download links. In Docker Compose the internal endpoint stays `http://minio:9000`, while the default public endpoint is `http://127.0.0.1:9000` so local browsers can resolve it. If you access PodFlow from another device, set `PCT_S3_PUBLIC_ENDPOINT` to a host or domain that device can reach.

`PCT_CREDENTIALS_ENCRYPTION_KEY` encrypts user-saved provider API keys. Keep it stable across `.env`, `.env.real`, and server deploy envs that share the same database. If it is empty, the app falls back to `PCT_SECRET_KEY`; changing either key after users save provider credentials means those credentials must be re-entered. New secrets are written as `pct-v2.` Fernet tokens; older `pct-v1.` records remain readable for local compatibility and are upgraded when users save the key again.

## Real Pipeline Mode

For the real AI pipeline, install optional pipeline dependencies:

```bash
pip install -e .[pipeline]
```

Then switch:

```bash
PCT_PIPELINE_MODE=real
```

`deploy/dockerfiles/Dockerfile.gpu` installs the optional `pipeline` dependency group for worker images that need the real processing stack.

For a local end-to-end real pipeline run with Docker Compose, use the root-level [LOCAL_REAL_PIPELINE.md](../LOCAL_REAL_PIPELINE.md) guide. It keeps local SMS mocked while enabling the real audio processing worker.

The voice-clone engine is selected via `PCT_VOICE_CLONE_PROVIDER` (also switchable per user in Profile):

- `elevenlabs` (default): ElevenLabs IVC creates one persisted voice per speaker; TTS reuses that voice id on resume.
- `voxcpm`: self-hosted open-source, zero-shot cloning straight from the speaker's local reference audio (no API key, no third-party voice retention). Requires a GPU (~8GB) and the optional extra: `pip install -e .[pipeline,voxcpm]`.
- `cosyvoice`: DashScope preset voices; also the fallback path when the main engine fails under `voice_clone_mode=best_effort`.

The local real overlay defaults to CPU-only PyTorch wheels for a more reliable first run on ordinary Docker Desktop machines. It also pins the pyannote/NumPy stack to versions that are compatible with `pyannote/speaker-diarization-3.1`. If you want GPU acceleration, override the `PIP_TORCH_INDEX_URL` and `PIP_TORCH_PACKAGES` values in `.env.real` with a matching CUDA PyTorch wheel set, then rebuild the worker.

After the real worker starts, a quick dependency smoke test is:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml exec worker python -c "import numpy, torch, torchaudio, pyannote.audio; from faster_whisper import WhisperModel; import demucs; print('real_imports=ok', numpy.__version__, torch.__version__, torchaudio.__version__, pyannote.audio.__version__)"
```

## Server Deployment

Two server-side compose files are included:

- `docker-compose.prod.yml`: production app stack only, intended for managed/external Postgres, Redis, and S3-compatible storage
- `docker-compose.demo.yml`: public demo stack with bundled Postgres, Redis, and MinIO

Common server preparation:

1. Copy the repo to the server deploy directory.
2. Copy `.env.prod.example` to `.env.prod` for production, or `.env.demo.example` to `.env.demo` for demo.
3. Set `PODFLOW_IMAGE_NAMESPACE` to your GHCR namespace, for example `ghcr.io/<your-github-owner>`.
4. Set `PODFLOW_IMAGE_TAG` if you want a specific image tag. Defaults are `main-latest` for prod and `demo-latest` for demo.
5. If GHCR packages are private, run `docker login ghcr.io` on the server first.

See [DEPLOY_ENV.md](DEPLOY_ENV.md) for ready-to-fill `.env.prod` and `.env.demo` templates plus field-by-field notes.

Production example:

```bash
cp .env.prod.example .env.prod
PODFLOW_IMAGE_NAMESPACE=ghcr.io/<your-github-owner> docker compose -f docker-compose.prod.yml pull
PODFLOW_IMAGE_NAMESPACE=ghcr.io/<your-github-owner> docker compose -f docker-compose.prod.yml up -d
```

Demo example:

```bash
cp .env.demo.example .env.demo
PODFLOW_IMAGE_NAMESPACE=ghcr.io/<your-github-owner> docker compose -f docker-compose.demo.yml pull
PODFLOW_IMAGE_NAMESPACE=ghcr.io/<your-github-owner> docker compose -f docker-compose.demo.yml up -d
```

Notes:

- In `docker-compose.demo.yml`, backend and worker automatically use the internal `postgres`, `redis`, and `minio` service addresses.
- For demo deployments, set `PCT_S3_PUBLIC_ENDPOINT` in `.env.demo` to a browser-reachable host, not `localhost`, if other devices need to open audio links.
- The GitHub deploy workflow now selects `docker-compose.prod.yml` for `main` and `docker-compose.demo.yml` for `demo`.

## Validation Checklist

Use this acceptance checklist after `docker compose up --build`:

1. Visit `http://localhost:8080/login`
2. Send an SMS code and log in
3. Upload a local audio file from the home page
4. Confirm the app redirects to `/tasks/{id}`
5. Confirm progress updates move through the pipeline
6. Confirm the task reaches `completed`
7. Confirm result playback works
8. Confirm result download works

Failure-path checks:

1. Stop the worker or inject an error
2. Confirm the task moves to `failed`
3. Confirm `error_message` is visible in the task detail page
4. Confirm quota is refunded once for the failed task
5. Trigger a provider-fixable error and confirm the task moves to `paused`, preserves quota, shows pause codes, and resumes after credentials or billing are fixed

## Backend Notes

- The worker now writes lifecycle state back to the database at task start, each stage transition, completion, and failure.
- Redis is the cross-process progress bus between workers and API websocket consumers.
- The websocket endpoint sends a DB snapshot first, then streams Redis events.
- `TaskRuntimeService` is the central runtime state writer for worker progress and persistence.
- Provider-fixable failures use `paused` plus `pause_reason_code` / `provider_error_code`; ordinary failures remain `failed` and refund quota once.
- Upload validation accepts only known audio file extensions and MIME types before quota is consumed.

## Frontend Notes

- In local `next dev`, the browser calls `http://127.0.0.1:8000/api/v1` directly by default for auth, user, task, and websocket traffic to avoid flaky dev-proxy behavior.
- In production builds and container deployments, the browser uses same-origin `/api` access.
- To call a backend directly from the browser, set `NEXT_PUBLIC_PCT_API_ORIGIN` in `frontend/.env.local`, for example `NEXT_PUBLIC_PCT_API_ORIGIN=http://127.0.0.1:8000`.
- In `next dev`, large task uploads bypass the Next rewrite proxy and go straight to the backend API. Override that target with `NEXT_PUBLIC_PCT_UPLOAD_API_ORIGIN=http://127.0.0.1:8000` if needed; when omitted it reuses `NEXT_PUBLIC_PCT_API_ORIGIN`.
- Task detail uses websocket updates first and polling as a fallback.
- Unfinished surfaces are hidden or clearly marked unavailable.

## CI Direction

The base package now excludes heavyweight AI dependencies. Real pipeline libraries live under the optional `pipeline` extra, which keeps mock-mode CI and Docker startup lighter and more reliable.
