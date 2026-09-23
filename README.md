# Guardarr

**Storage Admission & Protection for the *Arr ecosystem.**

Guardarr prevents automated media downloads from consuming the storage you still need.

## What it does

- Checks available storage before admitting new downloads
- Reserves space for requested content
- Tracks reservations through the download/import lifecycle
- Integrates with Sonarr, Radarr, Seerr and Jellyseerr
- Controls qBittorrent admission and tagging
- Detects unexpected/unreserved qBittorrent activity
- Reconciles filesystem and download state
- Fails closed when admission cannot be safely verified

## What it does not do

Guardarr is **not** a media cleanup or retention system.

- **qui** → torrent lifecycle
- **Reclaimerr** → media retention
- **Guardarr** → storage admission and protection

## Design principles

- Storage safety is deterministic
- AI/agents are never the safety authority
- Reservations are persistent and auditable
- Hardlinks and cross-seeds are handled conservatively
- Existing downloads are not deleted by Guardarr
- The emergency brake is independent of AI/orchestration

## Status

Guardarr is under active development. The core admission, reservation, qBittorrent, *Arr and Seerr/Jellyseerr integration layers are implemented and under verification.

## License

Open source.
