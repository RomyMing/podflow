# Deployment Env Guide

This guide explains how to fill server-side env files for PodFlow deployments.

## Production

Start from:

```bash
cp .env.prod.example .env.prod
```

Recommended production template:

```dotenv
PCT_APP_ENV=prod
PCT_APP_MODE=prod
PCT_AUTH_MODE=sms
PCT_ENABLE_SMS_LOGIN=true
PCT_SHOW_DEMO_BANNER=false
PCT_ENABLE_SAMPLE_TASKS=false
PCT_ALLOW_USER_UPLOAD=true
PCT_ENABLE_REAL_COST_FEATURES=true
PCT_DEMO_USER_PHONE=13800138000
PCT_DEMO_USER_NICKNAME=PodFlow Demo
PCT_DEFAULT_MONTHLY_QUOTA=5

PCT_SECRET_KEY=replace-with-a-long-random-secret
PCT_DATABASE_URL=postgresql+asyncpg://podflow:<db-password>@<db-host>:5432/podcast_translator
PCT_AUTO_MIGRATE_ON_STARTUP=true
PCT_REDIS_URL=redis://:<redis-password>@<redis-host>:6379/0
PCT_S3_ENDPOINT=https://<internal-s3-endpoint>
PCT_S3_PUBLIC_ENDPOINT=https://<public-s3-endpoint>
PCT_S3_BUCKET=podcast-translator-audio
PCT_S3_ACCESS_KEY=<s3-access-key>
PCT_S3_SECRET_KEY=<s3-secret-key>

PCT_PIPELINE_MODE=real
PCT_ENABLE_STALL_RECONCILER=false
PCT_WORKER_HEARTBEAT_INTERVAL_SECONDS=30
PCT_WORKER_LOCK_TTL_SECONDS=300
PCT_TASK_STALL_TIMEOUT_SECONDS=900
PCT_TASK_STALL_CONFIRMATION_SECONDS=300
PCT_TASK_STALL_SCAN_INTERVAL_SECONDS=60
PCT_TASK_STALL_SCAN_BATCH_SIZE=100
PCT_TRANSLATION_PROVIDER=deepseek
PCT_ASR_PROVIDER=whisper
PCT_TTS_PROVIDER=cosyvoice
PCT_VOICE_CLONE_PROVIDER=elevenlabs
PCT_ELEVENLABS_API_KEY=<elevenlabs-api-key>
PCT_ELEVENLABS_TTS_MODEL=eleven_multilingual_v2
PCT_ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
PCT_REQUIRE_VOICE_CLONE_CONSENT=true
PCT_HF_TOKEN=
PCT_DASHSCOPE_API_KEY=
PCT_DEEPSEEK_API_KEY=<deepseek-api-key>
PCT_DEEPSEEK_BASE_URL=https://api.deepseek.com

PCT_SMS_PROVIDER=aliyun
PCT_SMS_ACCESS_KEY_ID=<aliyun-access-key-id>
PCT_SMS_ACCESS_KEY_SECRET=<aliyun-access-key-secret>
PCT_SMS_SIGN_NAME=<sms-sign-name>
PCT_SMS_TEMPLATE_CODE=<sms-template-code>
```

Field notes:

- `PCT_SECRET_KEY`: use a long random string, and keep it stable after first deploy.
- `PCT_DATABASE_URL`: this should point to your managed or self-hosted production Postgres.
- `PCT_REDIS_URL`: this should point to your production Redis instance.
- `PCT_S3_ENDPOINT`: backend/worker internal access endpoint for object storage.
- `PCT_S3_PUBLIC_ENDPOINT`: browser-visible download/playback endpoint. Do not fill this with an internal-only address.
- `PCT_PIPELINE_MODE=real`: use the actual processing pipeline.
- `PCT_HF_TOKEN`: required when speaker diarization uses pyannote-backed flow.
- `PCT_DASHSCOPE_API_KEY`: required if `PCT_TTS_PROVIDER=cosyvoice`.
- `PCT_ELEVENLABS_API_KEY`: required when `PCT_VOICE_CLONE_PROVIDER=elevenlabs` and voice cloning is enabled.
- `PCT_DEEPSEEK_API_KEY`: required for translation.
- `PCT_SMS_*`: required when `PCT_SMS_PROVIDER=aliyun`. If you switch to `tencent`, update the provider and related implementation-side config together.
- `PCT_ENABLE_STALL_RECONCILER`: keep this `false` during the first deployment. Start the new `beat` service, wait until every active task is running on upgraded workers, then set it to `true` and restart only `beat`.
- Worker liveness defaults are heartbeat `30s`, owner lock `300s`, business-activity timeout `900s`, second confirmation `300s`, scan interval `60s`, and batch size `100`. Tune them only after observing real task-stage durations.
- The production worker image is built from `deploy/dockerfiles/Dockerfile.gpu` and installs the optional real pipeline dependency group. Make sure the production server has enough CPU/GPU, memory, disk, and provider network access before enabling `PCT_PIPELINE_MODE=real`.

Staged rollout order:

1. Back up the database and deploy the migration, API, worker, and the single `beat` service while reconciliation remains disabled.
2. Let old workers finish or stop them manually; verify all workers use the new image and that heartbeat/owner keys are being refreshed.
3. Simulate worker loss and Redis interruption in a test environment, then enable `PCT_ENABLE_STALL_RECONCILER=true` in production.
4. Monitor suspected stalls, confirmed stalls, automatic resumes, stale-worker rejections, dispatch failures, and one-time quota refunds.

## Demo

Start from:

```bash
cp .env.demo.example .env.demo
```

Recommended demo template:

```dotenv
PCT_APP_ENV=demo
PCT_APP_MODE=demo
PCT_AUTH_MODE=demo
PCT_ENABLE_SMS_LOGIN=false
PCT_SHOW_DEMO_BANNER=true
PCT_ENABLE_SAMPLE_TASKS=true
PCT_ALLOW_USER_UPLOAD=true
PCT_ENABLE_REAL_COST_FEATURES=false
PCT_DEMO_USER_PHONE=13800138000
PCT_DEMO_USER_NICKNAME=PodFlow Demo
PCT_DEFAULT_MONTHLY_QUOTA=999

PCT_SECRET_KEY=replace-with-a-long-random-secret
PCT_DATABASE_URL=postgresql+asyncpg://postgres:postgres_password@localhost:5432/podcast_translator
PCT_AUTO_MIGRATE_ON_STARTUP=true
PCT_REDIS_URL=redis://localhost:6379/0
PCT_S3_ENDPOINT=http://localhost:9000
PCT_S3_PUBLIC_ENDPOINT=https://<your-demo-domain>:9000
PCT_S3_BUCKET=podcast-translator-audio
PCT_S3_ACCESS_KEY=admin
PCT_S3_SECRET_KEY=change-minio-password

PCT_PIPELINE_MODE=mock
PCT_MOCK_PIPELINE_STAGE_DELAY_SECONDS=0.5
PCT_SMS_PROVIDER=mock
```

Field notes:

- In `docker-compose.demo.yml`, `PCT_DATABASE_URL`, `PCT_REDIS_URL`, and `PCT_S3_ENDPOINT` are overridden to internal container addresses automatically.
- You should still keep those values in `.env.demo` understandable for humans, but runtime will use the compose-injected internal endpoints.
- `PCT_S3_PUBLIC_ENDPOINT` must be reachable by the browser. If your demo site is public, do not leave it as `localhost`.
- `PCT_SECRET_KEY` should still be changed even for a demo server.
- `PCT_PIPELINE_MODE=mock` keeps the public demo cheap and stable.

## Front Door Variables

These variables are read by the compose files rather than the backend app itself:

```dotenv
PODFLOW_IMAGE_NAMESPACE=ghcr.io/<your-github-owner>
PODFLOW_IMAGE_TAG=main-latest
PODFLOW_HTTP_PORT=80
```

Demo-only extras:

```dotenv
PODFLOW_IMAGE_TAG=demo-latest
PODFLOW_HTTP_PORT=8080
PODFLOW_DEMO_POSTGRES_PASSWORD=change-postgres-password
PODFLOW_MINIO_API_PORT=9000
PODFLOW_MINIO_CONSOLE_PORT=9001
```

## Quick Checks

After the env file is ready:

```bash
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml up -d
```

Or for demo:

```bash
docker compose -f docker-compose.demo.yml config
docker compose -f docker-compose.demo.yml up -d
```

Then verify:

- Open `/health` through Nginx.
- Confirm login works in the expected mode.
- Create one task and watch it reach `completed`.
- Verify generated audio links open from another machine, not only from the server itself.
