# Local Real Pipeline Runbook

Use this guide to validate the real podcast translation chain on your local machine before buying production infrastructure.

## What Runs Locally

The local real stack uses:

- Postgres, Redis, and MinIO from `docker-compose.yml`
- API and frontend from `docker-compose.yml`
- Real worker from `docker-compose.real.yml`
- `PCT_PIPELINE_MODE=real`
- CPU-only PyTorch wheels by default for a stable first local run
- Mock SMS login, so you can focus on the audio pipeline first

The real worker installs the optional pipeline dependency group and runs Celery with `--concurrency=1`.
Model caches are persisted in a Docker volume so large downloads are reused across worker restarts. The worker Dockerfile also uses a BuildKit pip cache plus longer pip timeout/retry settings, because the real stack downloads several large audio/ML wheels.

## Machine Expectations

Minimum practical local test:

- 16 GB RAM or more
- 20-50 GB free disk
- Docker Desktop or Docker Engine
- A short audio file for the first test, ideally 30-60 seconds

Recommended:

- NVIDIA GPU for faster real processing
- Working Docker GPU runtime
- Stable network access to model/API providers

The checked-in `.env.real.example` starts with CPU-only `torch==2.2.2+cpu` and `torchaudio==2.2.2+cpu`. If you only have CPU, start with a very short audio file. Demucs, pyannote, and Whisper can be slow and memory-heavy.

## Required Accounts And Tokens

Prepare:

- DeepSeek API key
- Hugging Face token with access to pyannote speaker diarization models
- ElevenLabs API key for Instant Voice Cloning and primary TTS
- DashScope API key for CosyVoice fallback TTS

Accept any required Hugging Face model terms for:

- `pyannote/speaker-diarization-3.1`

## First-Time Setup

From repo root:

```bash
cd podcast_translator
cp .env.real.example .env.real
```

Edit `.env.real`:

```dotenv
PCT_TRANSLATION_PROVIDER=deepseek
PCT_DEEPSEEK_API_KEY=...
PCT_HF_TOKEN=...
PCT_VOICE_CLONE_PROVIDER=elevenlabs
PCT_ELEVENLABS_API_KEY=...
PCT_DASHSCOPE_API_KEY=...
```

Keep this for local validation:

```dotenv
PCT_CREDENTIALS_ENCRYPTION_KEY=<stable-key-shared-with-existing-local-db>
PCT_SMS_PROVIDER=mock
PCT_PIPELINE_MODE=real
PCT_ALLOW_USER_UPLOAD=true
```

If you already saved provider API keys while running the default `.env` stack, set `PCT_CREDENTIALS_ENCRYPTION_KEY` in `.env.real` to the same value that encrypted those keys before starting the real stack. Otherwise, delete and re-enter the provider keys from the Profile API key page.

Saved provider API keys are written as `pct-v2.` Fernet tokens. Older `pct-v1.` tokens are still readable so local databases from earlier runs can keep working, but any newly saved key is written as v2. Do not change `PCT_CREDENTIALS_ENCRYPTION_KEY` for a database that already contains saved provider credentials unless you are ready to re-enter those keys.

You can either put provider keys in `.env.real` as system defaults or save them per user in Profile > API management. Per-user keys take precedence over system keys for DeepSeek, OpenAI, ElevenLabs, Hugging Face, and DashScope. Tasks also run provider preflight before expensive stages; missing keys, invalid keys, exhausted quota, billing issues, unavailable object storage, or missing local runtime dependencies pause the task instead of marking it failed.

The real pipeline defaults to `PCT_VOICE_CLONE_PROVIDER=elevenlabs`. With `voice_clone_mode=best_effort`, failed ElevenLabs enrollment or synthesis falls back to CosyVoice. With `voice_clone_mode=required`, the task pauses so you can fix credentials, quota, or provider errors before resuming.

## Build And Start

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml up -d --build
```

For repeat starts after the worker image is already built:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml up -d --no-build
```

Open:

- App: `http://127.0.0.1:8080`
- Backend health: `http://127.0.0.1:8000/health`
- MinIO console: `http://127.0.0.1:9001`

MinIO default local credentials:

```text
admin / minio_password
```

## Dependency Defaults

The local real worker intentionally pins the fragile audio stack:

- `torch==2.2.2+cpu`
- `torchaudio==2.2.2+cpu`
- `numpy<2`
- `pyannote.audio>=3.1.0,<3.2.0`

This keeps the worker compatible with `pyannote/speaker-diarization-3.1` and avoids pulling very large CUDA wheels during the first local build.

After startup, verify the real dependencies inside the worker:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml exec worker python -c "import numpy, torch, torchaudio, pyannote.audio; from faster_whisper import WhisperModel; import demucs; print('real_imports=ok', numpy.__version__, torch.__version__, torchaudio.__version__, pyannote.audio.__version__)"
```

## Local Test Flow

1. Open `http://127.0.0.1:8080/login`.
2. Request an SMS code.
3. Because SMS is mock, check backend logs for the code if the UI requires it.
4. Upload a 30-60 second audio file.
5. Watch task detail progress.
6. Watch worker logs in another terminal:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml logs -f worker
```

7. Confirm the task reaches `completed`.
8. Play or download the generated output.

## Useful Commands

Check services:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml ps
```

Tail API logs:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml logs -f backend
```

Tail worker logs:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml logs -f worker
```

Stop services:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml down
```

Reset local data:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml down -v
```

Note: `down -v` also removes model caches. If you only want to reset app containers while keeping downloaded models, use:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml down
```

## GPU Check

The default local real build is CPU-only. If you expect GPU acceleration, first override `.env.real` with a CUDA-compatible `PIP_TORCH_INDEX_URL` and matching `PIP_TORCH_PACKAGES` values for both `torch` and `torchaudio`, then rebuild the worker.

Check the Docker GPU runtime:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Then check inside the worker:

```bash
docker compose --env-file .env.real -f docker-compose.yml -f docker-compose.real.yml exec worker python -c "import torch; print(torch.cuda.is_available())"
```

If this prints `False`, the worker is still running on CPU.

## Known Local Risks

- The P1 internal-test speaker range is 1-4 speakers. Leave `speaker_count=0` for pyannote auto-detection within that range, or explicitly choose 1-4.
- Voice cloning requires the uploader to confirm they have the right to process the audio and voices. Internal local runs can keep this relaxed, but production should set `PCT_REQUIRE_VOICE_CLONE_CONSENT=true`.
- ElevenLabs IVC creates reusable voice ids. Monitor retention and cleanup policy before expanding beyond internal validation.
- Provider keys are validated at key-save time and again during task preflight, but real provider availability can still fail later because of balance, quota, regional access, or model terms.
- Paused tasks keep their consumed quota and can be resumed after the provider issue is fixed. Failed tasks still refund quota once.
- Uploads are limited by allowed audio file extensions/MIME types and `PCT_MAX_UPLOAD_BYTES`; real audio duration is checked by the real pipeline after `ffprobe` can inspect the uploaded file.
- The first run may download large Python wheels and model files and take a long time.
- CPU-only local processing is expected to be much slower than a GPU-backed deployment.
- Repository files are UTF-8. If PowerShell displays Chinese comments as mojibake, verify with an UTF-8 reader before rewriting source text.
- Aliyun SMS is not needed for local real pipeline validation; keep `PCT_SMS_PROVIDER=mock`.

## Success Criteria

A local run counts as successful when:

- Upload succeeds.
- Worker enters every real stage.
- Final task status is `completed`.
- `speakers` and `segments` are persisted.
- `task_stage_runs` show completed stages and useful item progress for long translation/TTS work.
- Speaker detail shows voice provider, enrollment status, model, and fallback reason when fallback is used.
- Final audio URL opens in the browser.
- Output is understandable translated audio, speakers remain distinguishable, and the final MP3 is playable/downloadable.
