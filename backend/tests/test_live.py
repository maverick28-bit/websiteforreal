"""
Live Integration Tests (conditional on real API keys).

These tests run against actual AI providers (e.g. Gemini via LiteLLM)
only when valid non-placeholder API keys are set in LLM_API_KEYS.
If only placeholder keys exist, these tests are automatically skipped.
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

def _has_real_keys() -> bool:
    settings = get_settings()
    keys = settings.api_keys
    if not keys:
        return False
    # Check if keys are placeholders
    for k in keys:
        if "REPLACE" in k.upper() or "YOUR_KEY" in k.upper() or k.startswith("test_") or k.startswith("test"):
            return False
    return True


@pytest.mark.skipif(not _has_real_keys(), reason="Real API keys not configured in LLM_API_KEYS")
class TestLiveIntegration:
    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    def test_live_inference_call(self, client):
        resp = client.post(
            "/chat",
            json={"session_id": "s-live-e2e", "message": "Reply with 'Hello World' only."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert data["metadata"]["key_id"] in ("key_1", "key_2")
        assert data["metadata"]["input_tokens"] > 0
        assert data["metadata"]["output_tokens"] > 0

    def test_live_cache_hit_on_repeat(self, client):
        # First call in session 1
        msg = "What is the boiling point of water in Celsius? Answer in one word."
        resp1 = client.post("/chat", json={"session_id": "s-cache-live-1", "message": msg})
        assert resp1.status_code == 200

        # Second call in session 2 with identical message -> should hit LiteLLM cache
        resp2 = client.post("/chat", json={"session_id": "s-cache-live-2", "message": msg})
        assert resp2.status_code == 200
        assert resp2.json()["metadata"]["resolution_source"] == "LLM_CACHE"
        assert resp2.json()["metadata"]["key_id"] is None
        assert resp2.json()["reply"] == resp1.json()["reply"]
