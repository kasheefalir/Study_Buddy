from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    response_review_enabled: bool = os.getenv("RESPONSE_REVIEW_ENABLED", "false").lower() == "true"
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
    request_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT", "120"))
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "16"))
    context_window: int = int(os.getenv("CONTEXT_WINDOW", "16384"))
    response_tokens: int = int(os.getenv("RESPONSE_TOKENS", "1200"))
    data_dir: Path = Path(os.getenv("BUDDY_DATA_DIR", "data"))

    @property
    def conversations_dir(self) -> Path:
        return self.data_dir / "conversations"


settings = Settings()
