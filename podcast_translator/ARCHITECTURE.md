# PodFlow Architecture

> The authoritative, always-current architecture notes live in the repo-root
> [`CLAUDE.md`](../CLAUDE.md). This file is a stable high-level map; when in doubt,
> trust the code and `CLAUDE.md`.

## System shape

Async **FastAPI + Celery**. The API enqueues work; a Celery worker runs the long,
resumable AI pipeline. State lives in **Postgres** (SQLAlchemy async + Alembic) and
**S3-compatible object storage** (MinIO locally). Progress is pushed to the frontend
(Next.js) over **Redis**-backed websockets.

```
Next.js frontend ──HTTP──▶ FastAPI (src/api) ──▶ services ──▶ repositories ──▶ Postgres
                                  │                                   ▲
                                  └── enqueue tasks.run_pipeline ──▶ Celery worker
                                                                        │
                                          PipelineContext through 7 stages (src/pipeline)
                                                                        │
                                                          S3 artifacts + Redis progress
```

## The 7-stage pipeline (`src/pipeline/`)

vocal separation → speaker diarization → ASR → translation → voice-clone TTS →
temporal alignment → final mixing.

- `context.py` — `PipelineContext` + `TaskStage` (canonical, DB-persisted stage names).
- `base_stage.py` — `StageProcessor` chain of responsibility (checkpoint restore,
  state persistence, progress, failure handling).
- `orchestrator.py` / `long_audio.py` — non-chunked fallback vs. the default chunked
  long-audio path (`PCT_ENABLE_LONG_AUDIO_PIPELINE`).
- `strategies/` — pluggable per-stage providers; `voice_providers.py` holds the
  voice-clone engines (ElevenLabs / VoxCPM, with CosyVoice fallback).

## Two switches that change everything

- **`PCT_PIPELINE_MODE` (`mock` | `real`)** — read in `src/workers/tasks.py`. Mock
  fabricates speakers/segments/translations and copies source→output; it is used by
  local demos and **all CI**. Real runs the actual AI stages.
- **Resume & pause semantics** — jobs are resumable. Stages skip themselves when a
  valid checkpoint/artifact exists; TTS resumes per segment. Provider problems raise
  `TaskPausedError` → task `paused` (no quota refund); only resumable markers
  auto-resume a `failed` task.

## Cross-cutting

- **Credentials**: user provider keys are Fernet-encrypted (`src/core/credentials.py`,
  format `pct-v2`). `PCT_CREDENTIALS_ENCRYPTION_KEY` must be identical across every env
  sharing the same DB.
- **Retention/cleanup**: `ArtifactCleanupService` removes intermediate S3 objects and
  expired ElevenLabs voices (`PCT_VOICE_CLONE_RETENTION_DAYS`); see the
  `tasks.cleanup_expired_voices` Celery beat task and `scripts/cleanup_voices.py`.
- **Config**: all settings are `PCT_`-prefixed (`src/config.py`, pydantic-settings).
