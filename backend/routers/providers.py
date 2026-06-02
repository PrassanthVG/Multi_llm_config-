"""
Provider CRUD API.

POST   /api/providers/          — create provider (auto-registers with LiteLLM)
GET    /api/providers/          — list all providers
GET    /api/providers/{id}      — get single provider
PUT    /api/providers/{id}      — update provider (re-registers with LiteLLM)
DELETE /api/providers/{id}      — delete provider (deregisters from LiteLLM)
POST   /api/providers/{id}/activate   — set active=True
POST   /api/providers/{id}/deactivate — set active=False
POST   /api/providers/{id}/set-default — set as default LLM or VLM
GET    /api/providers/defaults/active  — returns current default LLM + VLM names
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.provider import Provider
from services.litellm_manager import litellm_manager

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────── #

class ProviderCreate(BaseModel):
    name: str
    display_name: str
    provider_type: str = "llm"   # "llm" or "vlm"
    model_name: str
    api_base: str
    api_key: str
    notes: Optional[str] = None
    is_active: bool = True


class ProviderUpdate(BaseModel):
    display_name: Optional[str] = None
    provider_type: Optional[str] = None
    model_name: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    notes: Optional[str] = None


class ProviderOut(BaseModel):
    id: int
    name: str
    display_name: str
    provider_type: str
    model_name: str
    api_base: str
    api_key: str
    is_active: bool
    is_default_llm: bool
    is_default_vlm: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ────────────────────────────────────────────────────────────── #

async def _get_or_404(db: AsyncSession, provider_id: int) -> Provider:
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Provider not found")
    return p


# ── Routes ─────────────────────────────────────────────────────────────── #

@router.post("/", response_model=ProviderOut, status_code=201)
async def create_provider(body: ProviderCreate, db: AsyncSession = Depends(get_db)):
    # Check name unique
    existing = await db.execute(select(Provider).where(Provider.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Provider name '{body.name}' already exists")

    p = Provider(**body.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)

    # Hot-register with LiteLLM
    if p.is_active:
        await litellm_manager.register_provider(p)

    return p


@router.get("/", response_model=list[ProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).order_by(Provider.created_at.desc()))
    return result.scalars().all()


@router.get("/defaults/active")
async def get_active_defaults(db: AsyncSession = Depends(get_db)):
    """Return the alias names of the current default LLM and VLM."""
    llm_result = await db.execute(
        select(Provider).where(Provider.is_default_llm == True, Provider.is_active == True)  # noqa: E712
    )
    vlm_result = await db.execute(
        select(Provider).where(Provider.is_default_vlm == True, Provider.is_active == True)  # noqa: E712
    )
    llm = llm_result.scalar_one_or_none()
    vlm = vlm_result.scalar_one_or_none()
    return {
        "default_llm": llm.name if llm else None,
        "default_vlm": vlm.name if vlm else None,
    }


@router.get("/{provider_id}", response_model=ProviderOut)
async def get_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_or_404(db, provider_id)


@router.put("/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: int, body: ProviderUpdate, db: AsyncSession = Depends(get_db)
):
    p = await _get_or_404(db, provider_id)
    old_name = p.name

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    p.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(p)

    # Re-register (deregister old name, register new config)
    await litellm_manager.deregister_provider(old_name)
    if p.is_active:
        await litellm_manager.register_provider(p)

    return p


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    p = await _get_or_404(db, provider_id)
    await litellm_manager.deregister_provider(p.name)
    await db.delete(p)
    await db.commit()


@router.post("/{provider_id}/activate", response_model=ProviderOut)
async def activate_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    p = await _get_or_404(db, provider_id)
    p.is_active = True
    p.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(p)
    await litellm_manager.register_provider(p)
    return p


@router.post("/{provider_id}/deactivate", response_model=ProviderOut)
async def deactivate_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    p = await _get_or_404(db, provider_id)
    p.is_active = False
    p.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(p)
    await litellm_manager.deregister_provider(p.name)
    return p


@router.post("/{provider_id}/set-default", response_model=ProviderOut)
async def set_default(provider_id: int, db: AsyncSession = Depends(get_db)):
    p = await _get_or_404(db, provider_id)

    if p.provider_type == "llm":
        # Clear all other LLM defaults
        await db.execute(
            update(Provider)
            .where(Provider.provider_type == "llm")
            .values(is_default_llm=False)
        )
        p.is_default_llm = True
    else:
        await db.execute(
            update(Provider)
            .where(Provider.provider_type == "vlm")
            .values(is_default_vlm=False)
        )
        p.is_default_vlm = True

    p.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(p)
    return p
