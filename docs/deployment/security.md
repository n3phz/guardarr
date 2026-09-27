# Security

## Deployment Security Properties

Guardarr's verified deployment architecture provides these security guarantees:

| Property | Status | Verification |
|----------|--------|--------------|
| `/data` read-only | ✅ | Volume mount `:ro` |
| `/config` RW (isolated) | ✅ | Dedicated volume |
| No Docker socket | ✅ | Not mounted in compose/role |
| Not privileged | ✅ | `privileged: false` (default) |
| Internal networking only | ✅ | `saltbox` / custom network |
| Non-root user | ✅ | PUID/PGID remap in entrypoint |
| Configuration separate from data | ✅ | `/config` vs `/data` |
| Secrets via env vars | ✅ | Never in image |

---

## Attack Surface

### Exposed
- **HTTP API** on port 8000 (intended for internal *Arr stack)
- **Health/Ready/Status** endpoints (no auth, monitoring only)

### Not Exposed
- Docker socket
- Host filesystem (except `/data` RO and `/config` RW)
- Database file (in `/config`, not exposed)
- qBittorrent credentials (only in env, used internally)

---

## Network Architecture

```
┌─────────────────────────────────────────────────┐
│              Docker Network (saltbox)           │
│  ┌─────────┐  ┌─────────┐  ┌────────────────┐  │
│  │ Guardarr│  │ qBittor │  │ Sonarr/Radarr    │  │
│  │  :8000  │  │  :8080  │  │ :8989 / :7878    │  │
│  └────┬────┘  └────┬────┘  └───────┬──────────┘  │
│       │            │               │             │
│       └────────────┴───────────────┘             │
│                    │                              │
│         ┌──────────┴──────────┐                  │
│         │     Seerr/Jelly     │                  │
│         │       :5055         │                  │
│         └─────────────────────┘                  │
└─────────────────────────────────────────────────┘
```

**No external ports** exposed by Guardarr itself — all communication is internal to the Docker network.

---

## Container User

Entrypoint remaps to PUID/PGID:

```bash
# docker-entrypoint.sh
PUID="${PUID:-100}"
PGID="${PGID:-101}"

if [ "$(id -u)" = "0" ]; then
    groupmod -o -g "$PGID" guardarr
    usermod -o -u "$PUID" -g guardarr guardarr
    exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups env HOME=/config "$@"
fi
```

**Result:** Process runs as non-root user with configurable UID/GID.

---

## Filesystem Permissions

| Path | Mode | Owner | Purpose |
|------|------|-------|---------|
| `/config` | RW | `guardarr:guardarr` | Database, config |
| `/data` | RO | `root:root` (host) | Monitored storage |
| `/downloads` | RW | `guardarr:guardarr` | qBittorrent saves |

**Note:** `/data` is read-only inside container — Guardarr only reads filesystem stats via `statvfs()`, never writes.

---

## Secrets Management

Secrets provided via environment variables:
- `QBITTORRENT_PASSWORD`
- `SONARR_API_KEY`
- `RADARR_API_KEY`
- `SEERR_API_KEY`
- `JELLYSEERR_API_KEY`

**Never** baked into image. Injected at container start via:
- Docker Compose `environment:`
- Saltbox `guardarr_role_docker_envs_custom`
- Kubernetes secrets (if deployed there)

---

## API Security

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `/api/health` | None | Monitoring |
| `/api/ready` | None | Orchestration |
| `/api/status` | None | Monitoring |
| `/api/*` (admission) | None* | Internal *Arr stack |

*All admission endpoints intended for internal use only. Deploy behind firewall/VPN if external access needed.

---

## Threat Model

| Threat | Mitigation |
|--------|------------|
| External API access | Internal Docker network only |
| Credential leakage | Env vars only, not in logs/image |
| Storage exhaustion | Admission floor + thresholds |
| Malicious reservation | Idempotency keys, unique index |
| qBittorrent takeover | Read-only `/data`, tagged torrents only |
| DB corruption | SQLite WAL mode, transactions |

---

## Compliance Notes

- No telemetry
- No external connections (except configured integrations)
- Audit log for all reservation changes
- Configurable data retention (manual cleanup)

---

## Next: [Health Checks](../verification/health.md)
