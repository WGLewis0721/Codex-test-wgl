"""Rate limiting for Workbench Gateway."""
from __future__ import annotations
import time
from collections import defaultdict, deque
from threading import Lock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from shared.config import get_settings

_settings = get_settings()
_lock = Lock()
# NOTE: This in-memory store is per-process. Use Redis for multi-worker deployments.
_request_times: dict[str, deque] = defaultdict(deque)


def is_rate_limited(client_id: str, limit: int | None = None, window_seconds: int = 60) -> bool:
    """Check if client has exceeded rate limit. Returns True if limited."""
    limit = limit or _settings.rate_limit_per_minute
    now = time.time()
    with _lock:
        q = _request_times[client_id]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def get_request_count(client_id: str) -> int:
    """Get current request count for a client."""
    with _lock:
        return len(_request_times.get(client_id, deque()))
