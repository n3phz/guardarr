import logging
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.core.config import get_settings

logger = logging.getLogger("guardarr.integrations.seerr")


class BaseSeerrClient(ABC):
    def __init__(self, base_url: str, api_key: str, timeout: int, verify_tls: bool):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.session = requests.Session()
        # Security: never log API key
        self.session.headers.update({
            "X-Api-Key": self.api_key,
            "Accept": "application/json"
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        url = f"{self.base_url}/api/v3/{endpoint.lstrip('/')}"
        try:
            response = self.session.request(method, url, timeout=self.timeout, verify=self.verify_tls, **kwargs)
            return response
        except Exception as e:
            # Security: ensure log never contains API key or Authorization headers
            logger.error(f"Seerr API request error ({method} {endpoint}): {e}")
            return None

    @abstractmethod
    def test_connectivity(self) -> Dict[str, Any]:
        pass


class SeerrClient(BaseSeerrClient):
    def __init__(self):
        settings = get_settings()
        super().__init__(
            base_url=settings.seerr_url,
            api_key=settings.seerr_api_key,
            timeout=settings.seerr_timeout_seconds,
            verify_tls=settings.seerr_verify_tls
        )

    def test_connectivity(self) -> Dict[str, Any]:
        response = self._request("GET", "system/status")
        if response and response.status_code == 200:
            try:
                data = response.json()
                return {"status": "connected", "version": data.get("version")}
            except Exception:
                return {"status": "connected", "version": "unknown"}
        return {"status": "disconnected", "reason": "Failed to connect or authenticate with Seerr"}


class JellyseerrClient(BaseSeerrClient):
    def __init__(self):
        settings = get_settings()
        super().__init__(
            base_url=settings.jellyseerr_url,
            api_key=settings.jellyseerr_api_key,
            timeout=settings.jellyseerr_timeout_seconds,
            verify_tls=settings.jellyseerr_verify_tls
        )

    def test_connectivity(self) -> Dict[str, Any]:
        response = self._request("GET", "system/status")
        if response and response.status_code == 200:
            try:
                data = response.json()
                return {"status": "connected", "version": data.get("version")}
            except Exception:
                return {"status": "connected", "version": "unknown"}
        return {"status": "disconnected", "reason": "Failed to connect or authenticate with Jellyseerr"}


def get_seerr_client(provider: str) -> BaseSeerrClient:
    if provider.lower() == "seerr":
        return SeerrClient()
    elif provider.lower() == "jellyseerr":
        return JellyseerrClient()
    else:
        raise ValueError(f"Unknown Seerr provider: {provider}")
