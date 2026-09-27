# Saltbox Deployment

## Overview

Saltbox is an opinionated media server automation framework. Guardarr provides a native Saltbox role for seamless integration.

## Prerequisites

- Saltbox deployed on target host
- `/mnt/unionfs` mergerfs mount available
- Docker network `saltbox` exists
- qBittorrent, Sonarr, Radarr, Seerr deployed via Saltbox

---

## Configuration

### 1. Enable Guardarr in `saltbox.yml`

```yaml
# saltbox.yml
- { role: guardarr, tags: ['guardarr'] }
```

### 2. Configure in `inventories/group_vars/all.yml`

```yaml
# Guardarr Integration Configuration

# Seerr API key — sourced from Seerr settings at deploy time
seerr_api_key: "{{ lookup('file', server_appdata_path + '/seerr/settings.json') | from_json | json_query('main.apiKey') }}"

# Sonarr API key — sourced from Sonarr config at deploy time
sonarr_api_key: "{{ lookup('file', server_appdata_path + '/sonarr/config.xml') | regex_search('(?<=<ApiKey>)[^<]+') }}"

# Radarr API key — sourced from Radarr config at deploy time
radarr_api_key: "{{ lookup('file', server_appdata_path + '/radarr/config.xml') | regex_search('(?<=<ApiKey>)[^<]+') }}"

# qBittorrent credentials — username from config, password from Saltbox accounts
qbittorrent_username: "{{ lookup('file', server_appdata_path + '/qbittorrent/qBittorrent/qBittorrent.conf') | regex_search('(?<=WebUI\\\\Username=)[^\n]+') | trim }}"
qbittorrent_password: "{{ user.pass }}"

# Guardarr custom environment — all integrations
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

### 3. Set Image Version

In `roles/guardarr/defaults/main.yml`:

```yaml
guardarr_role_docker_image_repo: "ghcr.io/n3phz/guardarr"
guardarr_role_docker_image_tag: "0.1.2"
```

**Verified digest:** `sha256:a3ff5813311f39d1610b4d956fea48a6f05fc38d3af7313343cf1f77a1a29077`

---

## Deployment

```bash
# From Saltbox directory
sudo ansible-playbook saltbox.yml --tags guardarr --skip-tags sanity-check
```

This will:
1. Pull `ghcr.io/n3phz/guardarr:0.1.2`
2. Create `/opt/guardarr` directory
3. Configure volumes:
   - `/opt/guardarr:/config` (RW)
   - `/mnt/unionfs:/data:ro` (RO)
   - `/mnt/unionfs/downloads:/downloads:rw` (RW)
4. Connect to `saltbox` Docker network
5. Set environment variables for all integrations
6. Start container with healthcheck

---

## Saltbox Role Defaults

Key defaults from `roles/guardarr/defaults/main.yml`:

```yaml
guardarr_instances: ["guardarr"]
guardarr_role_paths_folder: "{{ guardarr_name }}"
guardarr_role_paths_location: "{{ server_appdata_path }}/{{ guardarr_role_paths_folder }}"
guardarr_storage_path: "/mnt/unionfs"
guardarr_role_docker_container: "{{ guardarr_name }}"
guardarr_role_docker_image_pull: true
guardarr_role_docker_image_repo: "ghcr.io/n3phz/guardarr"
guardarr_role_docker_image_tag: "0.1.2"
guardarr_role_docker_restart_policy: unless-stopped
```

---

## Healthcheck

```yaml
guardarr_role_docker_healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
  interval: 30s
  timeout: 5s
  start_period: 10s
  retries: 3
```

---

## Volumes

| Host | Container | Mode |
|------|-----------|------|
| `/opt/guardarr` | `/config` | RW |
| `/mnt/unionfs` | `/data` | RO |
| `/mnt/unionfs/downloads` | `/downloads` | RW |

---

## Network

Connected to `saltbox` Docker network — enables internal DNS resolution:
- `http://seerr:5055`
- `http://sonarr:8989`
- `http://radarr:7878`
- `http://qbittorrent:8080`

---

## Security

| Property | Value |
|----------|-------|
| PUID/PGID | From Saltbox user config |
| `/data` | Read-only |
| `/downloads` | RW (for qBittorrent saves) |
| Docker socket | Not mounted |
| Privileged | False |
| Network | `saltbox` (internal) |

---

## Upgrading

```bash
# 1. Update version in roles/guardarr/defaults/main.yml
# 2. Commit and run
sudo ansible-playbook saltbox.yml --tags guardarr --skip-tags sanity-check
```

---

## Next: [Configuration](../deployment/configuration.md)
