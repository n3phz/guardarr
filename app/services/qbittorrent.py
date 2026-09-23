import logging
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from app.core.config import get_settings

logger = logging.getLogger("guardarr.qbittorrent")


class QBittorrentClient:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.qbittorrent_url.rstrip("/")
        self.username = self.settings.qbittorrent_username
        self.password = "***" # Redacted representation for safe internal usage
        self._raw_password = self.settings.qbittorrent_password
        self.timeout = self.settings.qbittorrent_timeout_seconds
        self.verify_tls = self.settings.qbittorrent_verify_tls
        self.session = requests.Session()

    def login(self) -> bool:
        login_url = f"{self.base_url}/api/v2/auth/login"
        try:
            response = self.session.post(
                login_url,
                data={"username": self.username, "password": self._raw_password},
                timeout=self.timeout,
                verify=self.verify_tls
            )
            if response.status_code == 200 and "Ok." in response.text:
                return True
            logger.warning(f"qBittorrent login failed: status {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"qBittorrent login exception: {e}")
            return False

    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        url = f"{self.base_url}/api/v2/{endpoint.lstrip('/')}"
        for attempt in range(2):
            try:
                response = self.session.request(method, url, timeout=self.timeout, verify=self.verify_tls, **kwargs)
                if response.status_code == 403 or "Unauthorized" in response.text:
                    if attempt == 0 and self.login():
                        continue
                return response
            except Exception as e:
                logger.error(f"qBittorrent request error ({method} {endpoint}): {e}")
                if attempt == 0 and self.login():
                    continue
                return None
        return None

    def test_connectivity(self) -> Dict[str, Any]:
        response = self._request("GET", "app/version")
        if response and response.status_code == 200:
            return {"status": "connected", "version": response.text.strip()}
        return {"status": "disconnected", "reason": "Failed to connect or authenticate with qBittorrent"}

    def get_torrents(self, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if tag:
            params["tag"] = tag
        response = self._request("GET", "torrents/info", params=params)
        if response and response.status_code == 200:
            try:
                return response.json()
            except Exception as e:
                logger.error(f"Failed to parse torrents JSON: {e}")
        return []

    def get_torrent_by_hash(self, torrent_hash: str) -> Optional[Dict[str, Any]]:
        torrents = self.get_torrents()
        for t in torrents:
            if t.get("hash", "").lower() == torrent_hash.lower():
                return t
        return None

    def add_torrent(
        self,
        url_or_magnet: str,
        savepath: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[str] = None,
        paused: bool = True
    ) -> bool:
        data: Dict[str, Any] = {
            "urls": url_or_magnet,
            "paused": "true" if paused else "false"
        }
        if savepath:
            data["savepath"] = savepath
        if category:
            data["category"] = category
        if tags:
            data["tags"] = tags

        response = self._request("POST", "torrents/add", data=data)
        if response and response.status_code == 200:
            return True
        return False

    def resume_torrents(self, hashes: List[str]) -> bool:
        data = {"hashes": "|".join(hashes)}
        response = self._request("POST", "torrents/resume", data=data)
        return response is not None and response.status_code == 200

    def add_torrent_tags(self, hashes: List[str], tags: List[str]) -> bool:
        data = {
            "hashes": "|".join(hashes),
            "tags": ",".join(tags)
        }
        response = self._request("POST", "torrents/addTags", data=data)
        return response is not None and response.status_code == 200
