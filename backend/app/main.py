"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import (
    get_history_for_llm,
    get_session_messages,
    init_db,
    save_message,
    session_exists,
)
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MessageOut,
    ResponseMetadata,
    SessionHistoryResponse,
)
from app.services.cache_service import init_cache, is_cache_enabled
from app.services.failover_service import parse_failure_header
from app.services.llm_service import AllProvidersUnavailable, call_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    init_db()
    init_cache()
    logger.info("DB and cache initialised")
    yield


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="LLM Chatbot API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            keys_configured=len(settings.api_keys),
            cache_enabled=is_cache_enabled(),
        )

    # ── Chat ──────────────────────────────────────────────────────────────────
    @app.post("/chat", response_model=ChatResponse)
    async def chat(
        body: ChatRequest,
        request: Request,
        x_simulate_failure: Optional[str] = Header(default=None),
    ) -> ChatResponse:
        cfg = get_settings()

        # Parse failure simulation header
        failures: dict = {}
        if cfg.enable_failure_simulation and x_simulate_failure:
            failures = parse_failure_header(x_simulate_failure)

        # Build message list for LLM
        system_prompt = body.system_prompt or cfg.default_system_prompt
        history = get_history_for_llm(body.session_id)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": body.message})

        # Call LLM with failover
        try:
            result = await call_llm(messages, failures=failures)
        except AllProvidersUnavailable:
            raise HTTPException(status_code=503, detail="all providers unavailable")
        except Exception as exc:
            logger.error("Unexpected LLM error: %s", exc)
            raise HTTPException(status_code=500, detail="internal server error")

        # Persist only on success
        save_message(body.session_id, "user", body.message)
        assistant_meta = {
            "resolution_source": "LLM_CACHE" if result.from_cache else "LIVE_INFERENCE",
            "model": result.model,
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "key_id": result.key_id,
            "fallback_attempts": result.fallback_attempts,
        }
        save_message(body.session_id, "assistant", result.reply, metadata=assistant_meta)

        return ChatResponse(
            session_id=body.session_id,
            reply=result.reply,
            metadata=ResponseMetadata(
                resolution_source="LLM_CACHE" if result.from_cache else "LIVE_INFERENCE",
                model=result.model,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                key_id=result.key_id,
                fallback_attempts=result.fallback_attempts,
            ),
        )

    # ── Session history ───────────────────────────────────────────────────────
    @app.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
    async def get_session_history(session_id: str) -> SessionHistoryResponse:
        if not session_exists(session_id):
            raise HTTPException(status_code=404, detail="session not found")
        raw = get_session_messages(session_id)
        messages = [MessageOut(**m) for m in raw]
        return SessionHistoryResponse(session_id=session_id, messages=messages)

    # ── Global error handler ──────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    return app


app = create_app()
