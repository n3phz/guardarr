# Project Context: Guardarr

## Identity
- **Name**: Guardarr
- **Repository**: https://github.com/n3phz/guardarr.git
- **Root**: /opt/openclaw/data/workspace/guardarr
- **Default Branch**: main
- **Current Commit**: 1132451edd1d429f8e4df138b946d844a07546b8

## Technology Stack
- **Language**: Python 3.11+ (primary), TypeScript (frontend)
- **Package Manager**: pip (Python), npm (frontend)
- **Framework**: FastAPI (backend), React 18 + Vite (frontend)
- **Container**: Dockerfile (multi-stage: Node 22 for frontend build, Python 3.13 slim for runtime)
- **CI/CD**: GitHub Actions (container build/push on release, MkDocs deploy to GitHub Pages on docs changes)

## Architecture
- **Type**: Web API + SPA (single-container deployment)
- **Components**:
  - **API Layer**: FastAPI with routers for health, readiness, status, reservations, qBittorrent, controlled admission, *Arr (Sonarr/Radarr), Seerr/Jellyseerr, audit, integrations
  - **Core**: Configuration (pydantic-settings), filesystem monitoring, threshold management
  - **Database**: SQLite with SQLAlchemy 2.0 + Alembic migrations
  - **Services**: Admission engine, *Arr orchestration, controlled admission, filesystem monitoring, qBittorrent control, reconciliation, Seerr orchestration
  - **Integrations**: *Arr (base), Seerr (base), qBittorrent
  - **Frontend**: React 18 SPA with Vite build, TypeScript, React Router, Vitest
- **Database**: SQLite (file-based at `/config/guardarr.db`), SQLAlchemy ORM, Alembic migrations in `migrations/`
- **Integrations**: qBittorrent (WebAPI), Sonarr/Radarr (API), Seerr/Jellyseerr (API)

## Infrastructure
- **Deployment**: Docker (single container), Docker Compose, Saltbox (Ansible role)
- **Orchestration**: docker-compose.yml (local), Saltbox Ansible role (production on saltbox2)
- **Hosts**:
  - `nph-visual-qa` (100.89.177.94) - Visual QA VM via SSH (user: visualqa, key: ~/.ssh/pve02_openclaw)
  - `saltbox2` (100.82.25.24) - Saltbox host via Tailscale
  - GitHub Container Registry (ghcr.io/n3phz/guardarr)
- **Networks**: Docker bridge network (default), Tailscale mesh (all nodes)
- **Storage**: 
  - Docker volumes: `guardarr-config` (config/db), `guardarr-storage` (monitored storage mount)
  - Saltbox: `/mnt/unionfs` (mergerfs unified storage) mounted read-only at `/data` in container
  - Config persisted at `/config` (bind-mounted from host appdata path)

## Environments
- **Development**:
  - Commands: `pip install -e ".[dev]"`, `pytest`, `npm run dev` (frontend on port 5173 with proxy to API on 8000)
  - Ports: API 8000, Frontend dev 5173
  - Test env: `.env.test` with low thresholds for fast tests
- **Staging**: Not explicitly defined; Saltbox deployment to saltbox2
- **Production**: 
  - Saltbox Ansible role deployment (pinned image tag: `ghcr.io/n3phz/guardarr:0.1.1`)
  - Docker Compose for standalone: `docker compose up -d`
  - Healthcheck: `/api/health` endpoint
  - PUID/PGID remapping via docker-entrypoint.sh (Saltbox-compatible)

## Access Mechanisms
- **SSH**: 
  - `github.com` (git operations, key: ~/.ssh/steam_trade_bot)
  - `nph-visual-qa` (100.89.177.94, user: visualqa, key: ~/.ssh/pve02_openclaw)
- **Tailscale**: All infrastructure nodes reachable via Tailscale mesh (pre30, pre34, pre35, saltbox2, pve01, pve02, nph-nas, etc.)
- **Docker**: Local Docker daemon; GHCR for published images
- **Secrets**: Mechanism only — `.env` file (from `.env.example` template), Saltbox inventory variables (uid, gid, tz), GitHub Actions secrets (GITHUB_TOKEN for GHCR)

## Commands
- **Install**: `pip install -e ".[dev]"` (backend), `cd webui && npm ci` (frontend)
- **Test**: `pytest` (backend), `cd webui && npm test` (frontend)
- **Build**: `cd webui && npm run build` (frontend), `docker build -t guardarr .` (container)
- **Lint**: Not explicitly configured (TypeScript strict mode in tsconfig.json, pytest for Python)
- **Deploy**: `docker compose up -d` (local), Saltbox playbook (production), GitHub Actions on release (container publish)

## Visual QA
- **Frontend**: React 18 + Vite + TypeScript
- **Build Output**: `webui/dist/` (served by FastAPI static files at `/assets/*` and SPA catch-all)
- **QA VM**: `nph-visual-qa` (100.89.177.94, SSH via Tailscale)
- **Browser Tool**: Vitest (unit), Playwright not yet configured

## Constraints & Decisions
- **Storage safety is deterministic** — no AI/agent override of admission decisions
- **Fail-closed admission** — refuses new admissions when storage safety cannot be verified
- **Conservative accounting** — assumes worst-case for hardlinks, cross-seeds, incomplete downloads
- **Reservations are persistent and auditable** — not transient calculations
- **Narrow responsibility** — Guardarr does not replace downloaders, cleanup, retention, or AI agents
- **Saltbox-compatible** — PUID/PGID remapping, read-only storage mount, standard appdata paths
- **Multi-stage Docker build** — frontend built in Node stage, copied to Python runtime
- **SPA served by FastAPI** — static assets at `/assets/*`, index.html catch-all for non-API routes
- **Database auto-initialization** — lifespan handler creates tables on startup (since 0.1.2)
- **Threshold ordering enforced** — warning > admission_floor > emergency > critical (validated at startup)

## Known Issues / Gaps
- Playwright/Cypress not configured for E2E Visual QA
- Staging environment not explicitly defined
- Frontend linting (ESLint/Prettier) not configured
- No explicit secret rotation mechanism documented

## Last Updated
- **Date**: 2026-09-28
- **Commit**: 1132451edd1d429f8e4df138b946d844a07546b8