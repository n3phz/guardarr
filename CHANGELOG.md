# Changelog

## [0.1.4] - 2026-09-28
### Added
- React/Vite WebUI (Dashboard, Reservations, Integrations, Reconciliation, Settings) shipped inside the runtime image.
- FastAPI serves the compiled SPA at `/` with a catch-all client-side route fallback.
- FastAPI serves hashed frontend bundles from `/assets` (correct MIME types) with `/api/*` taking precedence.
- Saltbox Guardarr role: Traefik router for `guardarr.neph.ovh` (HTTP redirect + HTTPS, Authelia on the UI, API prefix bypass).

### Fixed
- Docker build now runs the frontend build stage and copies `webui/dist` into the runtime image.
- `webui/node_modules` is no longer tracked in Git; a dedicated `webui/.gitignore` excludes build artifacts and dependencies.
- Version metadata aligned across `pyproject.toml`, FastAPI app, `/api/health` and WebUI.

## [0.1.2] - 2026-09-27
### Fixed
- Initialize SQLite database schema automatically during application startup.
- Fresh installations with empty /config directory now create tables before serving requests.
- Added FastAPI lifespan handler that calls Base.metadata.create_all(bind=engine) on startup.

## [0.1.1] - 2026-09-25
### Added
- Seerr 3.4.1 compatibility fix.
- Updated API namespace to `/api/v1/`.
- Changed connectivity check to use `settings/about` endpoint.
- Ensured `X-Api-Key` header is sent for Seerr/Jellyseerr requests.

## [0.1.0] - 2026-08-01
- Initial release.
