"""Rate limit por IP em memoria (Live-1.3), janela deslizante.

Suficiente para uma instancia. Atras de um proxy (Caddy/Cloudflare), o IP real
vem de X-Forwarded-For. Nao e barreira absoluta: e mitigacao de abuso.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request

from .config import settings


class RateLimiter:
    """Limitador de janela deslizante: no maximo `limit` eventos por `window` s."""

    def __init__(self, limit: int, window: float = 60.0) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """True se o evento cabe na janela; registra o acesso quando permite."""
        now = time.time()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


def client_ip(request: Request) -> str:
    """IP real do cliente, considerando o X-Forwarded-For do proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = RateLimiter(settings.rate_limit_per_min)
