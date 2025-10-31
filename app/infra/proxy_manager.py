from typing import Optional

from loguru import logger

from app.config import config


class ProxyManager:
    def __init__(self, proxies: list[str] | None = None):
        self.proxies = proxies or self._load_from_config()
        self.current_index = 0
        self.failed_proxies = set()

    def _load_from_config(self) -> list[str]:
        return getattr(config, "PROXY_POOL", [])

    def get_next_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None

        available = [p for p in self.proxies if p not in self.failed_proxies]
        if not available:
            logger.warning("All proxies failed, resetting pool")
            self.failed_proxies.clear()
            available = self.proxies

        proxy = available[self.current_index % len(available)]
        self.current_index += 1
        return proxy

    def mark_failed(self, proxy: str):
        self.failed_proxies.add(proxy)
        logger.warning(f"Proxy marked as failed: {proxy}")


class CloudflareBlockException(Exception):
    """CF block — rotation trigger."""

    pass
