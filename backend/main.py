"""
MuruganAI — Dynamic Provider Gateway
FastAPI backend: manages providers in DB, generates LiteLLM config, proxies calls.
"""

import os
import asyncio
import subprocess
import signal
import sys
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import providers, proxy, health
from services.litellm_manager import LiteLLMManager

litellm_manager = LiteLLMManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await litellm_manager.start()
    yield
    # Shutdown
    await litellm_manager.stop()


app = FastAPI(
    title="MuruganAI Provider Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(providers.router, prefix="/api/providers", tags=["providers"])
app.include_router(proxy.router, prefix="/api/proxy", tags=["proxy"])
app.include_router(health.router, prefix="/api/health", tags=["health"])

# Serve React frontend build
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
