"""
Backend test suite.

All LLM calls are mocked — no real API keys required.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Environment setup (must happen before importing app) ──────────────────────
os.environ.setdefault("LLM_API_KEYS", "test_key_1,test_key_2")
os.environ.setdefault("ENABLE_FAILURE_SIMULATION", "true")
os.environ.setdefault("LLM_MODEL", "gemini/gemini-2.0-flash")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

# Use a temp SQLite file so tests are isolated
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

# ── Import app after env is set ───────────────────────────────────────────────
from app.config import get_settings
from app.database import init_db
from app.main import app
from app.services.llm_service import AllProvidersUnavailable, LLMResult

get_settings.cache_clear()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_llm_result(
    reply: str = "Test reply",
    model: str = "gemini/gemini-2.0-flash",
    input_tokens: int = 10,
    output_tokens: int = 5,
    key_id: Optional[str] = "key_1",
    fallback_attempts: int = 0,
    latency_ms: int = 100,
    from_cache: bool = False,
) -> LLMResult:
    return LLMResult(
        reply=reply,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        key_id=key_id,
        fallback_attempts=fallback_attempts,
        latency_ms=latency_ms,
        from_cache=from_cache,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Each test gets its own temp database."""
    db_file = tmp_path / "test.db"
    with patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{db_file}"}):
        get_settings.cache_clear()
        init_db()
        yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── Health tests ──────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_structure(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["keys_configured"], int)
        assert data["keys_configured"] == 2
        assert isinstance(data["cache_enabled"], bool)
        assert data["cache_enabled"] is True


# ── Validation tests ──────────────────────────────────────────────────────────

class TestValidation:
    def test_empty_message_returns_422(self, client):
        resp = client.post("/chat", json={"session_id": "s1", "message": "   "})
        assert resp.status_code == 422

    def test_missing_session_id_returns_422(self, client):
        resp = client.post("/chat", json={"message": "hello"})
        assert resp.status_code == 422

    def test_message_too_long_returns_422(self, client):
        resp = client.post("/chat", json={"session_id": "s1", "message": "x" * 4001})
        assert resp.status_code == 422

    def test_session_id_too_long_returns_422(self, client):
        resp = client.post("/chat", json={"session_id": "x" * 129, "message": "hi"})
        assert resp.status_code == 422

    def test_valid_message_at_boundary(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result()
            resp = client.post("/chat", json={"session_id": "s1", "message": "x" * 4000})
            assert resp.status_code == 200


# ── Chat tests ────────────────────────────────────────────────────────────────

class TestChat:
    def test_successful_response_structure(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(reply="Paris")
            resp = client.post(
                "/chat",
                json={"session_id": "s1", "message": "What is the capital of France?"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "s1"
        assert data["reply"] == "Paris"
        meta = data["metadata"]
        assert "resolution_source" in meta
        assert "model" in meta
        assert "latency_ms" in meta
        assert "input_tokens" in meta
        assert "output_tokens" in meta
        assert "key_id" in meta
        assert "fallback_attempts" in meta

    def test_live_inference_source(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(from_cache=False, key_id="key_1")
            resp = client.post("/chat", json={"session_id": "s1", "message": "Hello"})
        assert resp.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"

    def test_message_trimming(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result()
            resp = client.post("/chat", json={"session_id": "s1", "message": "  hello  "})
        assert resp.status_code == 200
        # trimmed message is passed to LLM — messages arg should contain "hello"
        call_messages = mock_llm.call_args[0][0]
        user_msg = next(m for m in call_messages if m["role"] == "user")
        assert user_msg["content"] == "hello"


# ── Multi-turn / history tests ────────────────────────────────────────────────

class TestMultiTurn:
    def test_history_included_in_subsequent_calls(self, client):
        captured: List[List[dict]] = []

        async def fake_llm(messages, **kwargs):
            captured.append(list(messages))
            return _make_llm_result(reply=f"Response {len(captured)}")

        with patch("app.main.call_llm", side_effect=fake_llm):
            client.post("/chat", json={"session_id": "s-multi", "message": "First message"})
            client.post("/chat", json={"session_id": "s-multi", "message": "Second message"})

        assert len(captured) == 2
        # Second call must include First message and its response in history
        second_call_msgs = captured[1]
        contents = [m["content"] for m in second_call_msgs]
        assert "First message" in contents
        assert "Response 1" in contents
        assert "Second message" in contents

    def test_sessions_are_isolated(self, client):
        captured: Dict[str, List[List[dict]]] = {"A": [], "B": []}

        async def fake_llm_a(messages, **kwargs):
            captured["A"].append(list(messages))
            return _make_llm_result(reply="Reply A")

        async def fake_llm_b(messages, **kwargs):
            captured["B"].append(list(messages))
            return _make_llm_result(reply="Reply B")

        with patch("app.main.call_llm", side_effect=fake_llm_a):
            client.post("/chat", json={"session_id": "session-A", "message": "Hello from A"})

        with patch("app.main.call_llm", side_effect=fake_llm_b):
            client.post("/chat", json={"session_id": "session-B", "message": "Hello from B"})

        # Second call for B should NOT contain session A messages
        b_contents = [m["content"] for m in captured["B"][0]]
        assert "Hello from A" not in b_contents
        assert "Reply A" not in b_contents


# ── Session history endpoint tests ────────────────────────────────────────────

class TestSessionHistory:
    def test_unknown_session_returns_404(self, client):
        resp = client.get("/sessions/nonexistent-session-xyz/messages")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "session not found"

    def test_messages_returned_oldest_first(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(reply="R1")
            client.post("/chat", json={"session_id": "s-hist", "message": "First"})
            mock_llm.return_value = _make_llm_result(reply="R2")
            client.post("/chat", json={"session_id": "s-hist", "message": "Second"})

        resp = client.get("/sessions/s-hist/messages")
        assert resp.status_code == 200
        msgs = resp.json()["messages"]
        assert msgs[0]["content"] == "First"
        assert msgs[1]["content"] == "R1"
        assert msgs[2]["content"] == "Second"
        assert msgs[3]["content"] == "R2"

    def test_assistant_metadata_returned(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(reply="Metadata test")
            client.post("/chat", json={"session_id": "s-meta", "message": "Test"})

        resp = client.get("/sessions/s-meta/messages")
        msgs = resp.json()["messages"]
        assistant_msg = next(m for m in msgs if m["role"] == "assistant")
        assert "metadata" in assistant_msg
        assert "resolution_source" in assistant_msg["metadata"]
        assert "input_tokens" in assistant_msg["metadata"]
        assert "output_tokens" in assistant_msg["metadata"]


# ── Failover tests ────────────────────────────────────────────────────────────

class TestFailover:
    def test_key1_failure_key2_succeeds(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(
                key_id="key_2", fallback_attempts=1, from_cache=False
            )
            resp = client.post(
                "/chat",
                json={"session_id": "s-fail", "message": "Test failover"},
                headers={"X-Simulate-Failure": "key_1=429"},
            )
        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert meta["key_id"] == "key_2"
        assert meta["fallback_attempts"] == 1

    def test_all_keys_fail_returns_503(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = AllProvidersUnavailable("All failed")
            resp = client.post(
                "/chat",
                json={"session_id": "s-503", "message": "Test 503"},
                headers={"X-Simulate-Failure": "*=429"},
            )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "all providers unavailable"

    def test_failed_requests_not_stored(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = AllProvidersUnavailable("All failed")
            client.post(
                "/chat",
                json={"session_id": "s-no-store", "message": "Should not be stored"},
                headers={"X-Simulate-Failure": "*=429"},
            )
        # Session should not exist since it failed
        resp = client.get("/sessions/s-no-store/messages")
        assert resp.status_code == 404

    def test_fallback_attempts_count(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(
                key_id="key_2", fallback_attempts=1, from_cache=False
            )
            resp = client.post(
                "/chat",
                json={"session_id": "s-count", "message": "Count fallbacks"},
                headers={"X-Simulate-Failure": "key_1=500"},
            )
        assert resp.json()["metadata"]["fallback_attempts"] == 1


# ── Cache tests ───────────────────────────────────────────────────────────────

class TestCache:
    def test_cache_hit_returns_llm_cache(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(
                reply="Cached reply",
                from_cache=True,
                key_id=None,
                fallback_attempts=0,
            )
            resp = client.post("/chat", json={"session_id": "s-cache", "message": "Cache test"})

        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert meta["resolution_source"] == "LLM_CACHE"
        assert meta["key_id"] is None
        assert meta["fallback_attempts"] == 0

    def test_cache_hit_key_id_is_null(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(from_cache=True, key_id=None)
            resp = client.post("/chat", json={"session_id": "s-null", "message": "Cache null test"})
        assert resp.json()["metadata"]["key_id"] is None

    def test_live_inference_source(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(from_cache=False, key_id="key_1")
            resp = client.post("/chat", json={"session_id": "s-live", "message": "Live test"})
        assert resp.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"

    def test_cache_reply_identical(self, client):
        """Same response text from cache as original."""
        expected = "The capital of France is Paris."
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(reply=expected, from_cache=True, key_id=None)
            resp = client.post(
                "/chat",
                json={"session_id": "s-identical", "message": "Capital of France?"},
            )
        assert resp.json()["reply"] == expected

    def test_cache_token_usage_returned(self, client):
        with patch("app.main.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = _make_llm_result(
                from_cache=True, key_id=None, input_tokens=42, output_tokens=9
            )
            resp = client.post("/chat", json={"session_id": "s-tokens", "message": "Tokens"})
        meta = resp.json()["metadata"]
        assert meta["input_tokens"] == 42
        assert meta["output_tokens"] == 9
