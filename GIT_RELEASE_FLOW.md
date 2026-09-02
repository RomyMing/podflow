# Git Release Flow

> **Implementation history:** this describes the former private development and deployment flow. The public `RomyMing/podflow` repository is a reviewed release snapshot and does not deploy `main` or `demo`.

## Branches

- `main`
  - Real product route
  - Deploys to the production environment
- `demo`
  - Portfolio/demo route
  - Deploys to the public showcase environment
- `feature/*`
  - New features branch from `main`
- `fix/*`
  - Bug fixes branch from `main`
- `chore/*`
  - Tooling, CI, deployment, or maintenance changes

## Merge Rules

1. Build new features on `feature/*` from `main`.
2. Merge reviewed work into `main` first.
3. Sync `main` into `demo` when the feature is ready for public showcasing.
4. Keep `demo` limited to showcase-only changes such as:
   - demo login
   - demo banner
   - sample-task-first guidance
   - mock pipeline defaults

## Environment Files

Backend examples live in:

- `podcast_translator/.env.example`
- `podcast_translator/.env.demo.example`
- `podcast_translator/.env.prod.example`

Frontend examples live in:

- `podcast_translator/frontend/.env.example`
- `podcast_translator/frontend/.env.demo.example`
- `podcast_translator/frontend/.env.prod.example`

## GitHub Actions

- `.github/workflows/ci.yml`
  - Runs on `main` and `demo` pushes/PRs
  - Starts test services and runs backend/frontend validation
- `.github/workflows/deploy.yml`
  - `main` => `production` GitHub Environment
  - `demo` => `demo` GitHub Environment
  - `main` builds and pushes GHCR images, then deploys over SSH
  - `demo` pulls the branch on the server and builds local demo images
  - Production worker images are built from `podcast_translator/deploy/dockerfiles/Dockerfile.gpu` and include the optional real pipeline dependency group

## Required GitHub Environment Secrets

Configure these in both `production` and `demo` environments:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_PATH`

For private GHCR packages in `production`, also configure:

- `GHCR_USERNAME`
- `GHCR_TOKEN`

## Real Pipeline Rollout

Use [REAL_PIPELINE_ROLLOUT.md](./REAL_PIPELINE_ROLLOUT.md) before turning on `PCT_PIPELINE_MODE=real` in production.
