"""Optional OpenSearch integration with graceful fallback."""
from __future__ import annotations
from typing import Any
from .config import get_settings
from .logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()


def _get_client() -> Any | None:
    if not _settings.opensearch_enabled:
        return None
    try:
        from opensearchpy import OpenSearch
        return OpenSearch([_settings.opensearch_url])
    except ImportError:
        logger.warning("opensearch-py not installed; OpenSearch disabled")
        return None
    except Exception as exc:
        logger.warning(f"OpenSearch connection failed: {exc}")
        return None


def query_recent(
    index: str | None = None,
    minutes: int = 60,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Query recent events from OpenSearch. Returns empty list if disabled."""
    client = _get_client()
    if client is None:
        return []
    index = index or _settings.opensearch_index
    query = {
        "query": {
            "range": {
                "@timestamp": {"gte": f"now-{minutes}m", "lte": "now"}
            }
        },
        "size": top_k,
        "sort": [{"@timestamp": {"order": "desc"}}],
    }
    try:
        result = client.search(index=index, body=query)
        return [hit["_source"] for hit in result["hits"]["hits"]]
    except Exception as exc:
        logger.warning(f"OpenSearch query failed: {exc}")
        return []


def summarize_events(events: list[dict[str, Any]]) -> str:
    """Convert OpenSearch events to a text summary for LLM context."""
    if not events:
        return ""
    import json as _json
    lines = [f"- {_json.dumps(e)}" for e in events[:10]]
    return "Recent system events:\n" + "\n".join(lines)
