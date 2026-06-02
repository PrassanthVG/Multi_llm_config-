"""
LiteLLMManager — the core service.

Responsibilities:
  1. Generate litellm_config.yaml from active providers in DB.
  2. Start/stop the LiteLLM proxy as a subprocess.
  3. Register/deregister providers via LiteLLM Admin API (hot-reload, no restart).
  4. Health-check the proxy.
"""

import asyncio
import os
import subprocess
import signal
import logging
from pathlib import Path

import httpx
import yaml

from database import SessionLocal
from models.provider import Provider
from sqlalchemy import select

logger = logging.getLogger(__name__)

LITELLM_PORT = int(os.environ.get("LITELLM_PORT", "4000"))
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-murugan-gateway-2024")
LITELLM_BASE_URL = f"http://localhost:{LITELLM_PORT}"
CONFIG_PATH = Path("litellm_config.yaml")


class LiteLLMManager:
    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._client = httpx.AsyncClient(timeout=30)

    # ------------------------------------------------------------------ #
    #  Config generation                                                   #
    # ------------------------------------------------------------------ #

    async def generate_config(self) -> dict:
        """Build litellm_config.yaml content from active DB providers."""
        async with SessionLocal() as db:
            result = await db.execute(
                select(Provider).where(Provider.is_active == True)  # noqa: E712
            )
            providers = result.scalars().all()

        model_list = []
        for p in providers:
            model_list.append(
                {
                    "model_name": p.name,  # alias used by callers
                    "litellm_params": {
                        "model": f"openai/{p.model_name}",  # openai/ = OpenAI-compatible endpoint
                        "api_base": p.api_base,
                        "api_key": p.api_key,
                    },
                }
            )

        config = {
            "model_list": model_list,
            "litellm_settings": {
                "ssl_verify": False,
                "request_timeout": 120,
            },
            "general_settings": {
                "master_key": LITELLM_MASTER_KEY,
            },
        }
        return config

    async def write_config(self):
        config = await self.generate_config()
        CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False))
        logger.info("LiteLLM config written to %s", CONFIG_PATH)

    # ------------------------------------------------------------------ #
    #  Process management                                                  #
    # ------------------------------------------------------------------ #

    async def start(self):
        await self.write_config()
        self._process = subprocess.Popen(
            [
                "litellm",
                "--config", str(CONFIG_PATH),
                "--port", str(LITELLM_PORT),
                "--detailed_debug",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        logger.info("LiteLLM proxy started (pid=%s) on port %s", self._process.pid, LITELLM_PORT)

        # Wait until healthy (up to 30 s)
        for _ in range(30):
            await asyncio.sleep(1)
            if await self.is_healthy():
                logger.info("LiteLLM proxy is healthy.")
                return
        logger.warning("LiteLLM proxy did not become healthy within 30 s — continuing anyway.")

    async def stop(self):
        if self._process:
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
            logger.info("LiteLLM proxy stopped.")
        await self._client.aclose()

    async def restart(self):
        """Rewrite config and restart the proxy process."""
        await self.stop()
        await asyncio.sleep(1)
        await self.start()

    # ------------------------------------------------------------------ #
    #  Hot-reload via Admin API (preferred — no restart)                  #
    # ------------------------------------------------------------------ #

    async def register_provider(self, provider: Provider):
        """Add a provider to the running LiteLLM proxy without restart."""
        payload = {
            "model_name": provider.name,
            "litellm_params": {
                "model": f"openai/{provider.model_name}",
                "api_base": provider.api_base,
                "api_key": provider.api_key,
            },
        }
        try:
            r = await self._client.post(
                f"{LITELLM_BASE_URL}/model/new",
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                json=payload,
            )
            r.raise_for_status()
            logger.info("Registered provider '%s' with LiteLLM.", provider.name)
        except Exception as exc:
            logger.error("Failed to register provider '%s': %s", provider.name, exc)
            # Fall back to config-reload
            await self.write_config()

    async def deregister_provider(self, provider_name: str):
        """Remove a provider from the running LiteLLM proxy without restart."""
        try:
            r = await self._client.post(
                f"{LITELLM_BASE_URL}/model/delete",
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
                json={"id": provider_name},
            )
            r.raise_for_status()
            logger.info("Deregistered provider '%s' from LiteLLM.", provider_name)
        except Exception as exc:
            logger.error("Failed to deregister provider '%s': %s", provider_name, exc)
            await self.write_config()

    # ------------------------------------------------------------------ #
    #  Health                                                              #
    # ------------------------------------------------------------------ #

    async def is_healthy(self) -> bool:
        try:
            r = await self._client.get(f"{LITELLM_BASE_URL}/health/liveliness")
            return r.status_code == 200
        except Exception:
            return False

    async def get_models(self) -> list:
        """List all models registered in the proxy."""
        try:
            r = await self._client.get(
                f"{LITELLM_BASE_URL}/models",
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
            )
            r.raise_for_status()
            data = r.json()
            return data.get("data", [])
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    #  Proxy a completion call                                             #
    # ------------------------------------------------------------------ #

    async def chat_completion(self, model: str, messages: list, **kwargs) -> dict:
        payload = {"model": model, "messages": messages, **kwargs}
        r = await self._client.post(
            f"{LITELLM_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()


# Singleton — imported by routers
litellm_manager = LiteLLMManager()
