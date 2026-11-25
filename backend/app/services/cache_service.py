"""LiteLLM cache service — in-memory cache."""
from __future__ import annotations

import litellm
from litellm.caching.caching import Cache

_cache_enabled = False


def init_cache() -> None:
    """Initialize LiteLLM in-memory (local) cache."""
    global _cache_enabled
    # LiteLLM uses "local" for in-process in-memory cache
    litellm.cache = Cache(type="local")
    litellm.enable_cache()
    _cache_enabled = True


def is_cache_enabled() -> bool:
    return _cache_enabled
