# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

The actual application lives in `podcast_translator/`, not the repo root. The root holds product/design docs (`PROJECT_*.md`, `Design.md`, `PodFlow_PD.png`), the Chinese-language `README.md`, and the real-pipeline runbooks (`LOCAL_REAL_PIPELINE.md`, `REAL_PIPELINE_ROLLOUT.md`). **Run almost all commands from inside `podcast_translator/`.**

PodFlow is a podcast translation MVP: it takes an uploaded audio file and produces a playable/downloadable translated podcast through a 7-stage AI pipeline (vocal separation → speaker diarization → ASR → translation → voice-clone TTS → temporal alignment → final mixing).

## Commands

All backend commands run from `podcast_translator/`:

```bash
pip install -e .[dev]                 # backend + dev deps (pytest, ruff, mypy)
pip install -e .[pipeline]            # heavy real-pipeline deps (demucs, pyannote, faster-whisper, numpy<2)
pytest                                # full backend test suite (asyncio_mode=auto via pytest.ini)
pytest tests/unit/test_services/test_task_runtime_service.py   # one file
pytest tests/unit/test_services/test_task_runtime_service.py::test_name   # one test
ruff check src tests                  # lint (CI gate)
mypy src                              # type check
```

Frontend (from `podcast_translator/frontend/`):

```bash
npm ci          # install
npm run dev     # next dev --turbopack
npm run build   # production build (CI gate)
npm run lint    # next lint
```

CI lives at the **repo root** (`.github/workflows/ci.yml` — GitHub only runs root-level workflows). It runs `ruff check src tests` + `pytest` with `PCT_PIPELINE_MODE=mock`, plus `npm run build`. Tests require Postgres and run against `PCT_DATABASE_URL` (CI brings up the `postgres_test` service via `docker compose --profile test` on port 5433).

### Running the stack (Docker)

```bash
docker compose up --build           # default MOCK stack — no GPU/provider keys needed
```

App at `http://localhost:8080`, API health at `http://localhost:8000/health`, MinIO console at `http://localhost:9001` (`admin` / `minio_password`). Mock SMS login code is `123456`.

Real AI pipeline is an **overlay**, not the default compose file:

```bash
cp .env.real.example .env.real      # fill DeepSeek / HF / ElevenLabs / DashScope keys
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml up -d --build
```

See `LOCAL_REAL_PIPELINE.md` for the full runbook. Compose services: `postgres`, `redis`, `minio`, `backend` (FastAPI), `worker` (Celery), `frontend` (Next.js), `nginx`.

## Architecture

Async FastAPI + Celery system. The API enqueues work; a Celery worker runs the long-running pipeline. State lives in Postgres (SQLAlchemy async + Alembic) and S3-compatible object storage (MinIO locally); progress is pushed to the frontend over Redis-backed websockets.

**Mock vs. real is the most important runtime switch.** `PCT_PIPELINE_MODE` (`mock` | `real`) is read in `src/workers/tasks.py`. Mock mode (`_execute_mock_pipeline`) fabricates speakers/segments/translations and just copies the source to the output — used for local demos and all CI. Real mode runs the actual AI stages. CI and local default dev should assume mock unless explicitly testing the real path.

### Request → pipeline flow

1. `src/api/v1/` routers (`auth`, `users`, `tasks`, `transcripts`) → `src/services/` (business logic) → `src/repositories/` (DB access) → `src/models/` (SQLAlchemy).
2. Task creation enqueues `tasks.run_pipeline` (`src/workers/tasks.py`). The worker takes a Redis per-task lock, runs provider preflight (real mode), builds a `PipelineContext`, and executes the pipeline.
3. Progress/state writes go through `TaskRuntimeService` via `WorkerTaskLifecycleHooks` (`on_stage_started/progress/completed`, `persist_pipeline_state`). These hooks are attached to the `PipelineContext` and called by stages.

### The pipeline (`src/pipeline/`)

- **`context.py`** — `PipelineContext` (the dataclass threaded through all stages) and `TaskStage` enum. `TaskStage` values are the canonical stage names persisted to the DB and used as `start_stage` for resume.
- **`base_stage.py`** — `StageProcessor` ABC. Stages are a **chain of responsibility**: each holds a `next_processor` and calls it after `process()`. The base class handles checkpoint restore, state persistence, progress reporting, and failure handling — subclasses implement `process()` and `stage`.
- **`orchestrator.py`** — `PodcastTranslatorPipeline` builds the stage chain in reverse from a `start_stage`, truncating earlier stages for resume. Stages `s1`–`s7` live in `src/pipeline/stages/`.
- **`long_audio.py`** — `LongAudioPipeline`, the **default real path** when `PCT_ENABLE_LONG_AUDIO_PIPELINE=True`. Splits audio into overlapping chunks and runs the front-half stages concurrently (`PCT_AUDIO_CHUNK_SECONDS`, `PCT_CHUNK_PIPELINE_MAX_IN_FLIGHT`, `PCT_CHUNK_PIPELINE_STAGE_WORKERS`). The non-chunked `orchestrator` is the fallback.
- **`strategies/`** — pluggable provider implementations per stage: `separation/` (demucs), `asr/` (whisper, sensevoice), `translation/` (deepseek, openai_gpt), `tts/` (cosyvoice, fish_speech). The `s5` TTS stage also uses ElevenLabs IVC via `voice_providers.py`.
- **`checkpoint.py`** — stage-level checkpointing for resume.

### Resume & pause semantics (important, non-obvious)

The system is built around **resumable long jobs**, so changes here have wide impact:

- Stages skip themselves if a valid checkpoint or persisted artifact exists (`_restore_completed_stage`). `ctx.invalidated_stages` forces re-running a stage.
- TTS resumes per-segment (`synths/seg_{index}.mp3`); a long job that dies mid-TTS continues from completed segments. Final output object is `{task_id}/output/final_podcast.mp3` — if it already exists the worker marks the task completed and skips the pipeline.
- **Paused ≠ failed.** Provider problems (missing/invalid key, insufficient balance, exhausted quota, service down) raise `TaskPausedError` (`src/core/provider_errors.py`) and set the task to `paused` without refunding quota; the user fixes the provider and resumes from the current stage. `failed` tasks refund quota once and only auto-resume on resumable markers (`SoftTimeLimitExceeded`, `WorkerLostError`).

### Credentials encryption (handle with care)

User-level provider API keys are stored Fernet-encrypted (`src/core/credentials.py`, `user_api_key` model). Current format is `pct-v2`; `pct-v1` is read-only legacy and re-saving upgrades it. **`PCT_CREDENTIALS_ENCRYPTION_KEY` must stay identical across `.env`, `.env.real`, and any deployment sharing the same DB** — rotating it without re-collecting every user's keys breaks decryption.

## Configuration

All settings are `PCT_`-prefixed (`src/config.py`, pydantic-settings, loaded from `.env`). Required: `PCT_DATABASE_URL`, `PCT_REDIS_URL`, `PCT_S3_ENDPOINT`. Real pipeline adds provider keys (`PCT_DEEPSEEK_API_KEY`, `PCT_HF_TOKEN`, `PCT_ELEVENLABS_API_KEY`, `PCT_DASHSCOPE_API_KEY`) and `PCT_VOICE_CLONE_PROVIDER`. Supported speaker count is 1–4 (`speaker_count=0` auto-estimates).

`*.env*.example` files are templates; never commit real `.env.real`, `.env.prod`, `.env.demo`, or any provider token.
