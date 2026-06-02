"""
Provider DB model — stores all per-provider config.
Each row = one AI provider (LLM or VLM) with its own URL, model name, token.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Friendly name / alias — this is what main.py uses as model="..."
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Human-readable display name
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Provider type: "llm" or "vlm"
    provider_type: Mapped[str] = mapped_column(String(10), nullable=False, default="llm")

    # The actual model string sent to the provider (e.g. sorc/qwen3.5-instruct:latest)
    model_name: Mapped[str] = mapped_column(String(300), nullable=False)

    # Base URL (e.g. http://109.165.142.5:30203/v1)
    api_base: Mapped[str] = mapped_column(Text, nullable=False)

    # Bearer token / API key
    api_key: Mapped[str] = mapped_column(Text, nullable=False)

    # Whether this provider is registered in LiteLLM right now
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Whether this is the default provider for its type
    is_default_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default_vlm: Mapped[bool] = mapped_column(Boolean, default=False)

    # Optional notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
