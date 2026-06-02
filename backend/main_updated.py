"""
main.py — your existing AI pipeline file, UPDATED to use the provider gateway.

BEFORE (fragile):
    LLM_ENDPOINT = os.environ.get("DYNAMIC_LLM_URL", "http://109.165.142.5:30203/v1/chat/completions")
    TEXT_MODEL_NAME = os.environ.get("DYNAMIC_LLM_MODEL", "sorc/qwen3.5-instruct:latest")
    VL_MODEL_NAME   = os.environ.get("DYNAMIC_VLM_MODEL", ...)
    LLM_API_KEY     = os.environ.get("DYNAMIC_LLM_BEARER_TOKEN", "...")
    # 4 env vars per provider, different URLs, different tokens, restart to switch

AFTER (clean):
    GATEWAY_URL  = "http://localhost:8000"   # one fixed URL — forever
    GATEWAY_KEY  = "sk-murugan-gateway-2024" # one key — forever
    # Providers live in the DB. Switch by changing model alias. No restart.
"""

import os
import asyncio
from pathlib import Path
from typing import Union, Dict, Any

import httpx

# ── Gateway config (replaces all DYNAMIC_* env vars) ──────────────────── #

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")
GATEWAY_KEY = os.environ.get("GATEWAY_KEY", "sk-murugan-gateway-2024")

# Optional: override which provider alias to use at runtime.
# If not set, the gateway uses whatever is marked as default in the DB.
ACTIVE_LLM_ALIAS = os.environ.get("ACTIVE_LLM_ALIAS")   # e.g. "vast-llm", "scaleway-llm"
ACTIVE_VLM_ALIAS = os.environ.get("ACTIVE_VLM_ALIAS")   # e.g. "vast-vlm"

StructuredInput = Union[Dict[str, Any], str, Path]

# ── Client ─────────────────────────────────────────────────────────────── #

_client = httpx.AsyncClient(
    base_url=GATEWAY_URL,
    headers={"Authorization": f"Bearer {GATEWAY_KEY}"},
    timeout=120,
)


# ── Core call functions ─────────────────────────────────────────────────── #

async def call_llm(messages: list, model: str | None = None, **kwargs) -> dict:
    """
    Text/LLM call.
    If model is None → gateway picks the default LLM from DB.
    If model is set  → gateway routes to that exact provider alias.
    """
    payload = {
        "messages": messages,
        **kwargs,
    }
    if model or ACTIVE_LLM_ALIAS:
        payload["model"] = model or ACTIVE_LLM_ALIAS

    r = await _client.post("/api/proxy/chat", json=payload)
    r.raise_for_status()
    return r.json()


async def call_vlm(messages: list, model: str | None = None, **kwargs) -> dict:
    """
    Vision/VLM call — messages may include image_url content blocks.
    Gateway picks default VLM from DB unless overridden.
    """
    payload = {
        "messages": messages,
        **kwargs,
    }
    if model or ACTIVE_VLM_ALIAS:
        payload["model"] = model or ACTIVE_VLM_ALIAS

    r = await _client.post("/api/proxy/chat/vlm", json=payload)
    r.raise_for_status()
    return r.json()


async def call_explicit(model_alias: str, messages: list, **kwargs) -> dict:
    """Call a specific provider by alias (e.g. 'scaleway-llm', 'vast-vlm')."""
    payload = {"messages": messages, **kwargs}
    r = await _client.post(f"/api/proxy/chat/model/{model_alias}", json=payload)
    r.raise_for_status()
    return r.json()


# ── Convenience helpers (matching your existing pipeline style) ─────────── #

def _text_message(text: str) -> list:
    return [{"role": "user", "content": text}]


def _vision_message(text: str, image_url: str) -> list:
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ]


async def extract_text_from_doc(prompt: str, context: str) -> str:
    """Your existing doc extraction call — now provider-agnostic."""
    messages = [
        {"role": "system", "content": "You are a document extraction assistant."},
        {"role": "user", "content": f"{prompt}\n\n{context}"},
    ]
    resp = await call_llm(messages)
    return resp["choices"][0]["message"]["content"]


async def analyze_image(prompt: str, image_url: str) -> str:
    """Image analysis — automatically uses VLM provider."""
    messages = _vision_message(prompt, image_url)
    resp = await call_vlm(messages)
    return resp["choices"][0]["message"]["content"]


async def get_active_providers() -> dict:
    """Check which providers are currently default."""
    r = await _client.get("/api/providers/defaults/active")
    r.raise_for_status()
    return r.json()


# ── Demo ───────────────────────────────────────────────────────────────── #

async def main():
    # Check defaults
    defaults = await get_active_providers()
    print(f"Default LLM: {defaults['default_llm']}")
    print(f"Default VLM: {defaults['default_vlm']}")

    # Text call — uses default LLM from DB
    resp = await call_llm([{"role": "user", "content": "Hello, what model are you?"}])
    print("LLM:", resp["choices"][0]["message"]["content"])

    # Use a specific provider by alias
    resp2 = await call_explicit(
        "scaleway-llm",
        [{"role": "user", "content": "Hello from Scaleway provider"}],
    )
    print("Scaleway:", resp2["choices"][0]["message"]["content"])


if __name__ == "__main__":
    asyncio.run(main())
