"""Basic API tests (can run with MOCK_LLM=true)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Force mock mode for unit tests
os.environ["MOCK_LLM"] = "true"

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "endpoint" in r.json()


def test_classify_success():
    payload = {
        "text": "Нужен сайт для автосервиса с онлайн-записью. Бюджет 200 тысяч.",
        "source": "telegram",
        "received_at": "2026-08-03T10:00:00+03:00",
        "known_client_name": None,
        "known_contact": None,
        "language": "ru",
    }
    r = client.post("/api/leads/classify", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert "request_id" in data
    assert "data" in data
    assert data["data"]["service"] in {
        "Лендинг",
        "Корпоративный сайт",
        "Интернет-магазин",
        "Веб-сервис",
        "Telegram-бот",
        "Мобильное приложение",
        "Парсер / сбор данных",
        "AI-автоматизация",
        "CRM / бизнес-автоматизация",
        "Интеграция API",
        "Поддержка / доработка",
        "Консультация",
        "Другое",
        "Не определено",
    }


def test_classify_validation_error():
    r = client.post("/api/leads/classify", json={"text": ""})
    assert r.status_code == 422
