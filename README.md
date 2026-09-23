# Guardarr

Standalone open-source Arr-style application for storage admission and protection across the *Arr ecosystem.

## Features

- **Storage Monitoring** — Real-time filesystem statistics via `statvfs`
- **Threshold Management** — Configurable admission floor, warning, emergency, and critical thresholds
- **Inode Tracking** — Monitor inode exhaustion
- **REST API** — FastAPI-based endpoints for health, readiness, and status
- **Docker** — Single-container deployment with Docker Compose

## Quick Start

```bash
cp .env.example .env
docker compose up -d
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GUARDARR_DATA_DIR` | `/config` | Data directory for configuration and database |
| `GUARDARR_STORAGE_PATH` | `/data` | Path to monitored storage |
| `WARNING_THRESHOLD_BYTES` | `1000000000000` (1 TB) | Warning threshold |
| `ADMISSION_FLOOR_BYTES` | `750000000000` (750 GB) | Admission floor |
| `EMERGENCY_THRESHOLD_BYTES` | `500000000000` (500 GB) | Emergency threshold |
| `CRITICAL_THRESHOLD_BYTES` | `250000000000` (250 GB) | Critical threshold |
| `DATABASE_URL` | `sqlite:////config/guardarr.db` | Database URL |
| `TZ` | `UTC` | Timezone |

## API Endpoints

- `GET /api/health` — Health check
- `GET /api/ready` — Readiness check with filesystem validation
- `GET /api/status` — Full status with thresholds and inodes

## Threshold States

| State | Condition |
|-------|-----------|
| `NORMAL` | Available > Warning threshold |
| `WARNING` | Available ≤ Warning threshold |
| `BLOCKED` | Available ≤ Admission floor |
| `EMERGENCY` | Available ≤ Emergency threshold |
| `CRITICAL` | Available ≤ Critical threshold |

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
