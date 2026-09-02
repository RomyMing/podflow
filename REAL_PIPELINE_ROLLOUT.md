# Real Pipeline Rollout

> **Implementation history:** this rollout plan is retained for design context. The public repository does not provide a production deployment, hosted demo, or container registry publication.

This checklist turns the public demo into a production-capable podcast translation pipeline.

Local validation comes first. Before buying or wiring production infrastructure, use [LOCAL_REAL_PIPELINE.md](./LOCAL_REAL_PIPELINE.md) to prove the real audio pipeline works end to end on a local machine.

## Current Branch State

- `main` now contains the earlier local-real-pipeline work and is ahead of `demo`.
- `codex/stabilize-real-pipeline-wip` is the current stabilization branch for provider credentials, pause/resume, stage runs, upload limits, and documentation cleanup.
- `demo` remains the cheap public demo path with cloud demo deployment, mock pipeline, frontend demo mode, CI/CD, and task-state fixes.
- Keep `demo` cheap and stable with `PCT_PIPELINE_MODE=mock`.
- Use `main` for the real product path with `PCT_PIPELINE_MODE=real`.

## What Is Already Wired

- Task creation, upload, quota consumption, and async dispatch.
- Celery worker lifecycle updates.
- Redis-backed task progress fan-out.
- Pipeline stages for separation, diarization, ASR, translation, TTS, alignment, and mixing.
- User-level provider API key management for DeepSeek, OpenAI, ElevenLabs, Hugging Face, and DashScope.
- Provider preflight that pauses user-fixable provider failures instead of failing the task.
- Task pause/resume, stage run tracking, ETA display, and speaker voice metadata.
- ElevenLabs Instant Voice Cloning as the primary voice provider, with CosyVoice as `best_effort` fallback.
- 1-4 speaker diarization bounds, local reference audio selection, voice id reuse, and TTS segment reuse.
- Explicit upload extension/MIME validation plus byte-size limits.
- Public demo deployment on the `demo` branch.
- Production compose entrypoint on the `main` branch.

## Code Tasks

1. Land `codex/stabilize-real-pipeline-wip` after backend tests, frontend build, Alembic head check, and `git diff --check` pass.
2. Build production worker from `deploy/dockerfiles/Dockerfile.gpu`.
3. Keep CI on the mock pipeline so tests remain fast and stable.
4. Add a manually triggered real-pipeline smoke workflow with a short 2-speaker sample audio file and real provider secrets.
5. Keep `PCT_CREDENTIALS_ENCRYPTION_KEY` stable across every environment sharing a database; `pct-v2.` Fernet is now the write format and `pct-v1.` is read-only compatibility.
6. Keep `PCT_VOICE_CLONE_PROVIDER=elevenlabs` as the P1 default; add new provider implementations behind the same interface only after internal audio quality passes.
7. Implement real SMS provider support before public production login.
8. Add production queue controls beyond current worker limits: per-user concurrency, internal allowlist, and rate limits.
9. Extend current stage metrics into production monitoring: input file, output object, duration, provider, speaker count, clone success/fallback counts, TTS characters, cost, and failure reason.
10. Add cost ledger fields for provider spend, token counts, TTS billed characters, compute time, and manual intervention.

## GitHub Setup You Need To Do

1. Create or confirm GitHub Environments:
   - `demo`
   - `production`
   - optional: `staging`
2. Add environment secrets for both `demo` and `production`:
   - `DEPLOY_HOST`
   - `DEPLOY_USER`
   - `DEPLOY_SSH_KEY`
   - `DEPLOY_PATH`
3. For private GHCR packages, add production secrets:
   - `GHCR_USERNAME`
   - `GHCR_TOKEN`
4. Protect `main`:
   - Require pull request before merge.
   - Require CI to pass.
   - Disallow force push.
5. Protect `demo`:
   - Require CI to pass.
   - Allow direct deploy only after demo-specific review.

## Production Server Setup You Need To Do

1. Install Docker and Docker Compose v2.
2. If the real worker uses GPU, install:
   - NVIDIA driver
   - NVIDIA Container Toolkit
   - Docker GPU runtime support
   - A CUDA-compatible PyTorch stack inside the worker image, if GPU acceleration is required
3. Confirm the server can run:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

4. Validate whether `deploy/dockerfiles/Dockerfile.gpu` is fast enough for your workload. It installs the real pipeline dependency group, but GPU acceleration must still be verified against the final PyTorch/CUDA package set.
5. Prepare a production deploy directory matching `DEPLOY_PATH`.
6. Put `.env.prod` in the production deploy directory.
7. Use external production services where possible:
   - Postgres
   - Redis
   - S3-compatible object storage
8. Make `PCT_S3_PUBLIC_ENDPOINT` browser-reachable.
9. Make sure the server can reach model/API providers:
   - OpenAI or compatible endpoint
   - ElevenLabs
   - DashScope
   - Hugging Face
   - SMS provider API

## Required `.env.prod` Values

```dotenv
PCT_APP_ENV=prod
PCT_APP_MODE=prod
PCT_AUTH_MODE=sms
PCT_ENABLE_SMS_LOGIN=true
PCT_ALLOW_USER_UPLOAD=true
PCT_ENABLE_REAL_COST_FEATURES=true

PCT_PIPELINE_MODE=real
PCT_ASR_PROVIDER=whisper
PCT_TTS_PROVIDER=cosyvoice
PCT_VOICE_CLONE_PROVIDER=elevenlabs
PCT_TRANSLATION_PROVIDER=deepseek

PCT_SECRET_KEY=<long-random-secret>
PCT_CREDENTIALS_ENCRYPTION_KEY=<stable-key-shared-with-this-database>
PCT_DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<database>
PCT_REDIS_URL=redis://:<password>@<host>:6379/0
PCT_S3_ENDPOINT=<backend-s3-endpoint>
PCT_S3_PUBLIC_ENDPOINT=<browser-s3-endpoint>
PCT_S3_BUCKET=podcast-translator-audio
PCT_S3_ACCESS_KEY=<access-key>
PCT_S3_SECRET_KEY=<secret-key>

PCT_OPENAI_API_KEY=
PCT_OPENAI_BASE_URL=
PCT_DEEPSEEK_API_KEY=<deepseek-api-key>
PCT_DEEPSEEK_BASE_URL=https://api.deepseek.com
PCT_HF_TOKEN=<huggingface-token>
PCT_ELEVENLABS_API_KEY=<elevenlabs-api-key>
PCT_ELEVENLABS_TTS_MODEL=eleven_multilingual_v2
PCT_ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
PCT_VOICE_CLONE_RETENTION_DAYS=30
PCT_REQUIRE_VOICE_CLONE_CONSENT=true
PCT_DASHSCOPE_API_KEY=<dashscope-api-key>

PCT_SMS_PROVIDER=aliyun
PCT_SMS_ACCESS_KEY_ID=<aliyun-access-key-id>
PCT_SMS_ACCESS_KEY_SECRET=<aliyun-access-key-secret>
PCT_SMS_SIGN_NAME=<sms-sign-name>
PCT_SMS_TEMPLATE_CODE=<sms-template-code>
```

## Rollout Order

1. Demo remains live on `demo`.
2. Land the stabilization branch into `main`.
3. Deploy `main` to an internal production or staging server with `PCT_ALLOW_USER_UPLOAD=false`.
4. Run a real-pipeline smoke task using a short known 2-speaker audio file.
5. Enable upload for a small internal allowlist.
6. Confirm provider preflight, pause/resume, stage run display, and quota behavior on at least one provider-billing or invalid-key scenario.
7. Watch worker memory, GPU memory, task duration, Redis, and object storage growth.
8. Increase quota gradually after three internal 30-60 minute runs covering 2 speakers, 3-4 speakers, and background audio.
9. Only then expose SMS login publicly.

## Manual Smoke Test

After deploying `main`:

1. Open `/health`.
2. Log in with SMS.
3. Upload a 30-60 second podcast audio file.
4. Confirm progress moves through all stages.
5. Confirm segments and speakers are persisted.
6. Confirm each speaker shows voice provider, voice id/model, enrollment status, and fallback reason if fallback happened.
7. Confirm final audio is playable from a different machine.
8. Confirm failed tasks show `error_message` and refund quota once.
9. Confirm provider-fixable failures move to `paused`, preserve quota, show `pause_reason_code`, and resume from the paused stage after credentials/billing are fixed.

## Rollback

Use one of these rollback levers:

- Redeploy the previous `main-<sha>` image tag.
- Set `PCT_ALLOW_USER_UPLOAD=false`.
- Temporarily set `PCT_PIPELINE_MODE=mock` only for emergency product availability.
- Stop the worker service to prevent new processing while keeping the frontend/API online.
