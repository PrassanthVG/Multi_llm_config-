"""
Proxy router — the unified AI call endpoint.

Your main.py calls THIS instead of any raw provider URL.

POST /api/proxy/chat          — chat completion (auto-picks default LLM)
POST /api/proxy/chat/vlm      — vision completion (auto-picks default VLM)
POST /api/proxy/chat/model/{model_name} — explicit model alias
GET  /api/proxy/models        — list all models registered in LiteLLM
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.provider import Provider
from services.litellm_manager import litellm_manager

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────── #

class Message(BaseModel):
    role: str
    content: Any   # str for text, list for vision (image_url)


class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = None     # override default
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    extra: Optional[Dict[str, Any]] = None   # any provider-specific params


# ── Helpers ────────────────────────────────────────────────────────────── #

async def _resolve_model(
    db: AsyncSession,
    override: Optional[str],
    provider_type: str,
) -> str:
    if override:
        return override

    filter_col = Provider.is_default_llm if provider_type == "llm" else Provider.is_default_vlm
    result = await db.execute(
        select(Provider).where(filter_col == True, Provider.is_active == True)  # noqa: E712
    )
    p = result.scalar_one_or_none()
    if not p:
        # Fall back to any active provider of that type
        result2 = await db.execute(
            select(Provider).where(
                Provider.provider_type == provider_type,
                Provider.is_active == True,  # noqa: E712
            )
        )
        p = result2.scalar_one_or_none()

    if not p:
        raise HTTPException(
            status_code=503,
            detail=f"No active {provider_type.upper()} provider configured. "
                   "Add one via /api/providers/.",
        )
    return p.name


async def _call(model: str, req: ChatRequest) -> dict:
    kwargs: dict = {}
    if req.temperature is not None:
        kwargs["temperature"] = req.temperature
    if req.max_tokens is not None:
        kwargs["max_tokens"] = req.max_tokens
    if req.extra:
        kwargs.update(req.extra)

    messages = [m.model_dump() for m in req.messages]
    return await litellm_manager.chat_completion(model, messages, **kwargs)


# ── Routes ─────────────────────────────────────────────────────────────── #

@router.post("/chat")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Chat completion using the default LLM provider."""
    model = await _resolve_model(db, req.model, "llm")
    return await _call(model, req)


@router.post("/chat/vlm")
async def chat_vlm(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Vision completion using the default VLM provider."""
    model = await _resolve_model(db, req.model, "vlm")
    return await _call(model, req)


@router.post("/chat/model/{model_name}")
async def chat_explicit(model_name: str, req: ChatRequest):
    """Chat completion using an explicit model alias."""
    return await _call(model_name, req)


@router.get("/models")
async def list_proxy_models():
    """List all models registered in the running LiteLLM proxy."""
    return await litellm_manager.get_models()
