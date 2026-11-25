"""Pydantic request / response schemas."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Request bodies ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(...)
    system_prompt: Optional[str] = None

    @field_validator("message", mode="before")
    @classmethod
    def trim_and_validate_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) == 0:
            raise ValueError("message must not be empty after trimming whitespace")
        if len(v) > 4000:
            raise ValueError("message must be 4000 characters or fewer after trimming")
        return v


# ── Metadata ──────────────────────────────────────────────────────────────────

class ResponseMetadata(BaseModel):
    resolution_source: str            # "LIVE_INFERENCE" | "LLM_CACHE"
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: Optional[str]             # null on cache hits
    fallback_attempts: int


# ── Chat response ─────────────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: ResponseMetadata


# ── Session history ───────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    role: str
    content: str
    metadata: Optional[dict] = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[MessageOut]


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    keys_configured: int
    cache_enabled: bool
