"""In-memory token providers with auto-refresh support."""

import abc
import logging
import os
import threading

logger = logging.getLogger("http_proxy.providers")


class TokenProvider(abc.ABC):
    """Base class for token providers."""

    @abc.abstractmethod
    def get_token(self) -> str:
        """Return a valid token, refreshing if needed."""


class GcpTokenProvider(TokenProvider):
    """Provides GCP access tokens via Application Default Credentials.

    Caches credentials in memory and refreshes when expired.
    """

    def __init__(self, credentials=None, request_factory=None, scopes=None):
        self._lock = threading.Lock()
        self._scopes = scopes or ["https://www.googleapis.com/auth/cloud-platform"]
        self._credentials = credentials
        self._request_factory = request_factory

    def _get_request(self):
        if self._request_factory:
            return self._request_factory()
        import google.auth.transport.requests
        return google.auth.transport.requests.Request()

    def get_token(self) -> str:
        with self._lock:
            if self._credentials is None:
                import google.auth
                self._credentials, _ = google.auth.default(scopes=self._scopes)

            if not self._credentials.token or self._credentials.expired:
                self._credentials.refresh(self._get_request())

            return self._credentials.token


class EnvTokenProvider(TokenProvider):
    """Provides tokens from environment variables. Cached after first read."""

    def __init__(self, env_var: str):
        self._env_var = env_var
        self._lock = threading.Lock()
        self._cached: str | None = None

    def get_token(self) -> str:
        with self._lock:
            if self._cached is not None:
                return self._cached

            value = os.environ.get(self._env_var)
            if not value:
                raise ValueError(f"Environment variable {self._env_var} not set")

            self._cached = value
            return self._cached


# --- Module-level singleton ---

_providers: dict[str, TokenProvider] = {}


def setup() -> None:
    """Initialize token providers. Call once at startup."""
    global _providers
    _providers = {
        "github": EnvTokenProvider("GITHUB_TOKEN"),
        "gcp": GcpTokenProvider(),
        "slack": EnvTokenProvider("SLACK_TOKEN"),
    }
    logger.info("Token providers initialized")


def get_token(key: str) -> str | None:
    """Get a token by provider key. Returns None if provider not found or token unavailable."""
    provider = _providers.get(key)
    if provider is None:
        return None
    try:
        return provider.get_token()
    except Exception:
        logger.warning("Failed to get token for %s", key, exc_info=True)
        return None
