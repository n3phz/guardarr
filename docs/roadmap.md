# Roadmap

Guardarr's roadmap is driven by the *Arr ecosystem's evolving needs and real-world deployment feedback.

---

## 0.1.x — Foundation (Current)

| Feature | Status |
|---------|--------|
| Core admission engine | ✅ |
| SQLite persistence | ✅ |
| qBittorrent controlled add | ✅ |
| Seerr/Jellyseerr integration | ✅ |
| Sonarr/Radarr integration | ✅ |
| Reconciliation (reservations) | ✅ |
| qBittorrent reconciliation | ✅ |
| Docker deployment | ✅ |
| Saltbox role | ✅ |
| Health/ready/status endpoints | ✅ |
| Database auto-initialization | ✅ (0.1.2) |

---

## 0.2.x — Reliability & Observability

| Feature | Target | Notes |
|---------|--------|-------|
| **Metrics endpoint** (`/metrics`) | 0.2.0 | Prometheus format for storage, reservations, admission rates |
| **Structured logging** | 0.2.0 | JSON logs with correlation IDs |
| **Reconciliation scheduler** | 0.2.0 | Built-in periodic reconciliation (configurable interval) |
| **Webhook support** | 0.2.1 | *Arr webhook → Guardarr admit (no polling) |
| **Multi-device support** | 0.2.1 | Multiple monitored storage paths |

---

## 0.3.x — Advanced Admission

| Feature | Target | Notes |
|---------|--------|-------|
| **Priority admission** | 0.3.0 | Priority field used for tiebreaking |
| **Quota per user/adapter** | 0.3.0 | Per-owner/adapters capacity limits |
| **Predictive admission** | 0.3.1 | ML-based forecasting (optional, off by default) |
| **Cross-seed awareness** | 0.3.1 | Detect and account for cross-seeded torrents |

---

## 0.4.x — Ecosystem Expansion

| Feature | Target | Notes |
|---------|--------|-------|
| **Prowlarr integration** | 0.4.0 | Indexer-level admission |
| **Overseerr native** | 0.4.0 | First-class Overseerr support |
| **Whisparr support** | 0.4.0 | Adult media support |
| **Readarr support** | 0.4.1 | Audiobook support |

---

## 1.0 — Production Hardening

| Feature | Target | Notes |
|---------|--------|-------|
| **PostgreSQL support** | 1.0.0 | Optional, for HA deployments |
| **HA/Cluster mode** | 1.0.0 | Multiple Guardarr instances, shared DB |
| **Web UI** | 1.0.0 | Dashboard for reservations, status, manual operations |
| **RBAC** | 1.0.0 | Role-based access for UI/API |
| **Audit export** | 1.0.0 | Compliance-ready audit logs |

---

## Non-Goals

Guardarr will **not** implement:

| Feature | Reason |
|---------|--------|
| Media deletion/cleanup | Reclaimerr's domain |
| Torrent lifecycle management | qui's domain |
| AI-based admission | Safety boundary must be deterministic |
| Replacing *Arr stack | Guardarr protects, doesn't replace |
| Autonomous override of safety | Fail-closed is non-negotiable |

---

## How to Contribute

1. Check [Issues](https://github.com/n3phz/guardarr/issues) for open tasks
2. Fork, create feature branch
3. Add tests for new behavior
4. Ensure `pytest` passes
5. Submit PR with clear description

---

## Release Cadence

- **Patch** (0.1.x): Bug fixes, security — as needed
- **Minor** (0.2.x, 0.3.x): Features — ~monthly
- **Major** (1.0): Breaking changes — when ready

---

*Roadmap is aspirational. Priorities shift based on deployment feedback and ecosystem changes.*
