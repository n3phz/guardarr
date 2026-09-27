# Docker Deployment

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/n3phz/guardarr
cd guardarr
cp .env.example .env
# Edit .env with your settings

# 2. Deploy
docker compose up -d

# 3. Verify
curl http://localhost:8000/api/health
curl http://localhost:8000/api/ready
curl http://localhost:8000/api/status
```

---

## Docker Compose

```yaml
# docker-compose.yml
services:
  guardarr:
    build: .
    image: guardarr:latest
    container_name: guardarr
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - GUARDARR_DATA_DIR=/config
      - GUARDARR_STORAGE_PATH=/data
      - WARNING_THRESHOLD_BYTES=1000000000000
      - ADMISSION_FLOOR_BYTES=750000000000
      - EMERGENCY_THRESHOLD_BYTES=500000000000
      - CRITICAL_THRESHOLD_BYTES=250000000000
      - DATABASE_URL=sqlite:////config/guardarr.db
      - TZ=UTC
      
      # qBittorrent
      - QBITTORRENT_URL=http://qbittorrent:8080
      - QBITTORRENT_USERNAME=admin
      - QBITTORRENT_PASSWORD=adminadmin
      - QBITTORRENT_TIMEOUT_SECONDS=10
      - QBITTORRENT_VERIFY_TLS=true
      - QBITTORRENT_TORRENT_TAG_PREFIX=guardarr:
      
      # Sonarr
      - SONARR_URL=http://sonarr:8989
      - SONARR_API_KEY=sonarr_mock_key
      - SONARR_TIMEOUT_SECONDS=10
      - SONARR_VERIFY_TLS=true
      
      # Radarr
      - RADARR_URL=http://radarr:7878
      - RADARR_API_KEY=radarr_mock_key
      - RADARR_TIMEOUT_SECONDS=10
      - RADARR_VERIFY_TLS=true
      
      # Seerr
      - SEERR_URL=http://seerr:8990
      - SEERR_API_KEY=seerr_mock_key
      - SEERR_TIMEOUT_SECONDS=10
      - SEERR_VERIFY_TLS=true
      
      # Jellyseerr
      - JELLYSEERR_URL=http://jellyseerr:8991
      - JELLYSEERR_API_KEY=jellyseerr_mock_key
      - JELLYSEERR_TIMEOUT_SECONDS=10
      - JELLYSEERR_VERIFY_TLS=true
    volumes:
      - guardarr-config:/config
      - guardarr-storage:/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 5s

volumes:
  guardarr-config:
  guardarr-storage:
```

---

## Using Pre-built Image

```yaml
services:
  guardarr:
    image: ghcr.io/n3phz/guardarr:0.1.2
    # ... rest same as above
```

**Verified digest:** `sha256:a3ff5813311f39d1610b4d956fea48a6f05fc38d3af7313343cf1f77a1a29077`

---

## Environment Variables

### Core
| Variable | Default | Description |
|----------|---------|-------------|
| `GUARDARR_DATA_DIR` | `/config` | Config/database directory |
| `GUARDARR_STORAGE_PATH` | `/data` | Monitored storage path |
| `DATABASE_URL` | `sqlite:////config/guardarr.db` | SQLite database |
| `TZ` | `UTC` | Timezone |

### Thresholds
| Variable | Default | Description |
|----------|---------|-------------|
| `WARNING_THRESHOLD_BYTES` | `1000000000000` | Warning threshold |
| `ADMISSION_FLOOR_BYTES` | `750000000000` | Admission floor |
| `EMERGENCY_THRESHOLD_BYTES` | `500000000000` | Emergency threshold |
| `CRITICAL_THRESHOLD_BYTES` | `250000000000` | Critical threshold |

### qBittorrent
| Variable | Default |
|----------|---------|
| `QBITTORRENT_URL` | `http://localhost:8080` |
| `QBITTORRENT_USERNAME` | `admin` |
| `QBITTORRENT_PASSWORD` | `adminadmin` |
| `QBITTORRENT_TIMEOUT_SECONDS` | `10` |
| `QBITTORRENT_VERIFY_TLS` | `true` |
| `QBITTORRENT_TORRENT_TAG_PREFIX` | `guardarr:` |

### Sonarr
| Variable | Default |
|----------|---------|
| `SONARR_URL` | `http://localhost:8989` |
| `SONARR_API_KEY` | `sonarr_mock_key` |
| `SONARR_TIMEOUT_SECONDS` | `10` |
| `SONARR_VERIFY_TLS` | `true` |

### Radarr
| Variable | Default |
|----------|---------|
| `RADARR_URL` | `http://localhost:7878` |
| `RADARR_API_KEY` | `radarr_mock_key` |
| `RADARR_TIMEOUT_SECONDS` | `10` |
| `RADARR_VERIFY_TLS` | `true` |

### Seerr
| Variable | Default |
|----------|---------|
| `SEERR_URL` | `http://localhost:8990` |
| `SEERR_API_KEY` | `seerr_mock_key` |
| `SEERR_TIMEOUT_SECONDS` | `10` |
| `SEERR_VERIFY_TLS` | `true` |

### Jellyseerr
| Variable | Default |
|----------|---------|
| `JELLYSEERR_URL` | `http://localhost:8991` |
| `JELLYSEERR_API_KEY` | `jellyseerr_mock_key` |
| `JELLYSEERR_TIMEOUT_SECONDS` | `10` |
| `JELLYSEERR_VERIFY_TLS` | `true` |

---

## Volume Mounts

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `./config` | `/config` | RW | Database, config |
| `/mnt/storage` | `/data` | RO | Monitored storage |

---

## Network

Guardarr must share a Docker network with qBittorrent, Sonarr, Radarr, Seerr:

```yaml
networks:
  media-stack:
    external: true

services:
  guardarr:
    networks:
      - media-stack
```

---

## Healthchecks

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 5s
```

Endpoints:
- `/api/health` — Basic health
- `/api/ready` — Readiness with filesystem
- `/api/status` — Full status

---

## Security Notes

- `/data` mounted **read-only** inside container
- No Docker socket mounted
- Container runs as non-root user (PUID/PGID)
- Not privileged
- Internal Docker networking only

---

## Next: [Saltbox Deployment](saltbox.md)
