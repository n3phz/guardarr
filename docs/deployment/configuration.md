# Configuration Reference

All configuration is via environment variables. See [Docker Deployment](../deployment/docker.md) for the full compose file.

---

## Environment Variable Groups

### Core
| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GUARDARR_DATA_DIR` | `/config` | No | Data directory for database and config |
| `GUARDARR_STORAGE_PATH` | `/data` | No | Monitored storage path (read-only in container) |
| `DATABASE_URL` | `sqlite:////config/guardarr.db` | No | SQLite database URL |
| `TZ` | `UTC` | No | Timezone for timestamps |

### Storage Thresholds
| Variable | Default (bytes) | Human | Description |
|----------|----------------|-------|-------------|
| `WARNING_THRESHOLD_BYTES` | 1,000,000,000,000 | ~931 GiB | Warning state threshold |
| `ADMISSION_FLOOR_BYTES` | 750,000,000,000 | ~698 GiB | Admission floor (hard block) |
| `EMERGENCY_THRESHOLD_BYTES` | 500,000,000,000 | ~465 GiB | Emergency state |
| `CRITICAL_THRESHOLD_BYTES` | 250,000,000,000 | ~232 GiB | Critical state |

**Ordering:** `WARNING > ADMISSION_FLOOR > EMERGENCY > CRITICAL` (enforced at startup)

### qBittorrent
| Variable | Default | Description |
|----------|---------|-------------|
| `QBITTORRENT_URL` | `http://localhost:8080` | qBittorrent WebUI URL |
| `QBITTORRENT_USERNAME` | `admin` | WebUI username |
| `QBITTORRENT_PASSWORD` | `adminadmin` | WebUI password |
| `QBITTORRENT_TIMEOUT_SECONDS` | `10` | Request timeout |
| `QBITTORRENT_VERIFY_TLS` | `true` | Verify TLS certificates |
| `QBITTORRENT_TORRENT_TAG_PREFIX` | `guardarr:` | Tag prefix for managed torrents |

### Sonarr
| Variable | Default | Description |
|----------|---------|-------------|
| `SONARR_URL` | `http://localhost:8989` | Sonarr URL |
| `SONARR_API_KEY` | `sonarr_mock_key` | Sonarr API key |
| `SONARR_TIMEOUT_SECONDS` | `10` | Request timeout |
| `SONARR_VERIFY_TLS` | `true` | Verify TLS |

### Radarr
| Variable | Default | Description |
|----------|---------|-------------|
| `RADARR_URL` | `http://localhost:7878` | Radarr URL |
| `RADARR_API_KEY` | `radarr_mock_key` | Radarr API key |
| `RADARR_TIMEOUT_SECONDS` | `10` | Request timeout |
| `RADARR_VERIFY_TLS` | `true` | Verify TLS |

### Seerr
| Variable | Default | Description |
|----------|---------|-------------|
| `SEERR_URL` | `http://localhost:8990` | Seerr URL |
| `SEERR_API_KEY` | `seerr_mock_key` | Seerr API key |
| `SEERR_TIMEOUT_SECONDS` | `10` | Request timeout |
| `SEERR_VERIFY_TLS` | `true` | Verify TLS |

### Jellyseerr
| Variable | Default | Description |
|----------|---------|-------------|
| `JELLYSEERR_URL` | `http://localhost:8991` | Jellyseerr URL |
| `JELLYSEERR_API_KEY` | `jellyseerr_mock_key` | Jellyseerr API key |
| `JELLYSEERR_TIMEOUT_SECONDS` | `10` | Request timeout |
| `JELLYSEERR_VERIFY_TLS` | `true` | Verify TLS |

---

## Configuration Files

### .env.example
```bash
# Core
GUARDARR_DATA_DIR=/config
GUARDARR_STORAGE_PATH=/data
DATABASE_URL=sqlite:////config/guardarr.db
TZ=UTC

# Thresholds
WARNING_THRESHOLD_BYTES=1000000000000
ADMISSION_FLOOR_BYTES=750000000000
EMERGENCY_THRESHOLD_BYTES=500000000000
CRITICAL_THRESHOLD_BYTES=250000000000

# qBittorrent
QBITTORRENT_URL=http://qbittorrent:8080
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD=adminadmin
QBITTORRENT_TIMEOUT_SECONDS=10
QBITTORRENT_VERIFY_TLS=true
QBITTORRENT_TORRENT_TAG_PREFIX=guardarr:

# Sonarr
SONARR_URL=http://sonarr:8989
SONARR_API_KEY=your_key_here
SONARR_TIMEOUT_SECONDS=10
SONARR_VERIFY_TLS=true

# Radarr
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your_key_here
RADARR_TIMEOUT_SECONDS=10
RADARR_VERIFY_TLS=true

# Seerr
SEERR_URL=http://seerr:8990
SEERR_API_KEY=your_key_here
SEERR_TIMEOUT_SECONDS=10
SEERR_VERIFY_TLS=true

# Jellyseerr
JELLYSEERR_URL=http://jellyseerr:8991
JELLYSEERR_API_KEY=your_key_here
JELLYSEERR_TIMEOUT_SECONDS=10
JELLYSEERR_VERIFY_TLS=true
```

---

## Saltbox Configuration

In `inventories/group_vars/all.yml`:

```yaml
seerr_api_key: "{{ lookup('file', server_appdata_path + '/seerr/settings.json') | from_json | json_query('main.apiKey') }}"
sonarr_api_key: "{{ lookup('file', server_appdata_path + '/sonarr/config.xml') | regex_search('(?<=<ApiKey>)[^<]+') }}"
radarr_api_key: "{{ lookup('file', server_appdata_path + '/radarr/config.xml') | regex_search('(?<=<ApiKey>)[^<]+') }}"
qbittorrent_username: "{{ lookup('file', server_appdata_path + '/qbittorrent/qBittorrent/qBittorrent.conf') | regex_search('(?<=WebUI\\\\Username=)[^\n]+') | trim }}"
qbittorrent_password: "{{ user.pass }}"

guardarr_role_docker_envs_custom:
  SEERR_URL: "http://seerr:5055"
  SEERR_API_KEY: "{{ seerr_api_key }}"
  SONARR_URL: "http://sonarr:8989"
  SONARR_API_KEY: "{{ sonarr_api_key }}"
  RADARR_URL: "http://radarr:7878"
  RADARR_API_KEY: "{{ radarr_api_key }}"
  QBITTORRENT_URL: "http://qbittorrent:8080"
  QBITTORRENT_USERNAME: "{{ qbittorrent_username }}"
  QBITTORRENT_PASSWORD: "{{ qbittorrent_password }}"
```

---

## Validation

At startup, Guardarr validates:

1. Threshold ordering: `WARNING > ADMISSION_FLOOR > EMERGENCY > CRITICAL`
2. Filesystem accessibility: `GUARDARR_STORAGE_PATH` must exist and be readable
3. Database connectivity: `DATABASE_URL` must be valid SQLite path

Failures cause immediate startup exit with clear error messages.

---

## Next: [Security](security.md)
