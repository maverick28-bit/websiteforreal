"""LLM service: calls LiteLLM with per-key failover and cache awareness."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import litellm
from litellm.exceptions import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ServiceUnavailableError,
)

from app.config import get_settings
from app.services.failover_service import should_simulate_failure

# Status codes that trigger fallback to next key
RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


class SimulatedFailureError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"Simulated failure: HTTP {status_code}")


class AllProvidersUnavailable(Exception):
    pass


@dataclass
class LLMResult:
    reply: str
    model: str
    input_tokens: int
    output_tokens: int
    key_id: Optional[str]
    fallback_attempts: int
    latency_ms: int
    from_cache: bool


def _is_retryable(exc: Exception) -> bool:
    """Decide whether this exception should trigger key fallback."""
    if isinstance(exc, SimulatedFailureError):
        return exc.status_code in RETRYABLE_STATUS_CODES
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, ServiceUnavailableError):
        return True
    if isinstance(exc, AuthenticationError):
        return True  # bad key → try next
    # Check for timeout errors
    if isinstance(exc, (litellm.Timeout, TimeoutError)):
        return True
    if "timeout" in str(exc).lower():
        return True
    # Check status_code attribute if present
    status = getattr(exc, "status_code", None)
    if status and int(status) in RETRYABLE_STATUS_CODES:
        return True
    return False


async def call_llm(
    messages: List[dict],
    failures: Optional[Dict[str, int]] = None,
) -> LLMResult:
    """
    Try each configured API key in order. Return on first success.
    Raises AllProvidersUnavailable if every key fails.
    """
    settings = get_settings()
    api_keys = settings.api_keys
    model = settings.llm_model

    if not api_keys:
        raise AllProvidersUnavailable("No API keys configured")

    failures = failures or {}
    fallback_attempts = 0
    last_error: Optional[Exception] = None

    for idx, raw_key in enumerate(api_keys):
        key_id = f"key_{idx + 1}"

        # ── Simulate failure if requested ─────────────────────────────────
        sim_code = should_simulate_failure(key_id, failures)
        if sim_code:
            last_error = SimulatedFailureError(sim_code)
            fallback_attempts += 1
            continue

        # ── Attempt real LLM call ─────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=raw_key,
                caching=True,
                timeout=25,
            )
        except Exception as exc:
            import traceback
            logger = __import__("logging").getLogger(__name__)
            logger.error("LLM call failed for %s: %s: %s", key_id, type(exc).__name__, exc)
            if _is_retryable(exc):
                last_error = exc
                fallback_attempts += 1
                continue
            raise  # Non-retryable errors bubble up
        finally:
            pass

        latency_ms = int((time.perf_counter() - t0) * 1000)

        # ── Determine if response came from cache ─────────────────────────
        from_cache = False
        cache_hit = getattr(response, "_hidden_params", {}).get("cache_hit", False)
        if cache_hit:
            from_cache = True

        # ── Extract token usage ───────────────────────────────────────────
        usage = response.usage or {}
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0

        reply = response.choices[0].message.content or ""
        resp_model = response.model or model

        return LLMResult(
            reply=reply,
            model=resp_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            key_id=None if from_cache else key_id,
            fallback_attempts=0 if from_cache else fallback_attempts,
            latency_ms=latency_ms,
            from_cache=from_cache,
        )

    raise AllProvidersUnavailable(str(last_error) if last_error else "All keys failed")
