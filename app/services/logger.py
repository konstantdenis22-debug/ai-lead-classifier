from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_request(
    *,
    request_id: str,
    source: str,
    text: str,
    model: str,
    prompt_version: str,
    schema_version: str,
    api_latency_ms: Optional[float],
    http_status: Optional[int],
    retries: int,
    json_valid: bool,
    status: str,
    error: Optional[str] = None,
    tokens: Optional[dict] = None,
) -> None:
    """
    Записывает технический лог обработки заявки (ТЗ §11).
    Никогда не логирует API-ключ, секреты и содержимое .env.
    """
    settings = get_settings()
    log_file = settings.log_path / "processing.jsonl"

    entry: dict[str, Any] = {
        "request_id": request_id,
        "processed_at": _now_iso(),
        "source": source,
        "text": text[:2000],  # safety truncate
        "model": model,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "api_latency_ms": api_latency_ms,
        "http_status": http_status,
        "retries": retries,
        "json_valid": json_valid,
        "status": status,
        "error": error,
        "tokens": tokens,
    }

    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
