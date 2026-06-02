"""
Health endpoints.
"""

from fastapi import APIRouter
from services.litellm_manager import litellm_manager

router = APIRouter()


@router.get("/")
async def health():
    proxy_up = await litellm_manager.is_healthy()
    return {
        "gateway": "ok",
        "litellm_proxy": "healthy" if proxy_up else "unreachable",
        "litellm_url": f"http://localhost:4000",
    }
