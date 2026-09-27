# Changelog

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
