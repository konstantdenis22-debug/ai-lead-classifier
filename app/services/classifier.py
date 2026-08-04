from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Optional, Union

import jsonschema
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import (
    LEAD_CARD_JSON_SCHEMA,
    ClassifyRequest,
    ErrorDetail,
    ErrorResponse,
    LeadCard,
    SuccessResponse,
)
from app.services.logger import log_request
from app.services.routerai import RouterAIClient, RouterAIError


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8")


def _build_user_prompt(payload: ClassifyRequest) -> str:
    template = _load_prompt("user_template.txt")
    schema_str = json.dumps(LEAD_CARD_JSON_SCHEMA, ensure_ascii=False, indent=2)
    return (
        template.replace("{{source}}", payload.source.value)
        .replace("{{received_at}}", payload.received_at)
        .replace("{{known_client_name}}", str(payload.known_client_name))
        .replace("{{known_contact}}", str(payload.known_contact))
        .replace("{{language}}", payload.language or "ru")
        .replace("{{text}}", payload.text)
        .replace("{{schema}}", schema_str)
    )


def _mock_response(payload: ClassifyRequest) -> str:
    """Simple deterministic mock for offline testing."""
    text_lower = payload.text.lower()
    service = "Не определено"
    if "магазин" in text_lower or "ecom" in text_lower or "shop" in text_lower:
        service = "Интернет-магазин"
    elif "сайт" in text_lower or "site" in text_lower:
        service = "Корпоративный сайт"
    elif "бот" in text_lower or "bot" in text_lower:
        service = "Telegram-бот"
    elif "ai" in text_lower or "автоматиз" in text_lower:
        service = "AI-автоматизация"

    data = {
        "request_summary": f"Обработка заявки: {payload.text[:80]}...",
        "service": service,
        "industry": None,
        "project_type": "Новый проект",
        "required_features": [],
        "integrations": [],
        "budget_min_rub": None,
        "budget_max_rub": None,
        "deadline_text": None,
        "deadline_date": None,
        "urgency": "не определено",
        "client_name": payload.known_client_name,
        "company_name": None,
        "contact": None,
        "contact_value": payload.known_contact,
        "lead_quality": "тёплый",
        "missing_questions": ["Уточните бюджет и сроки?"],
        "confidence": 0.75,
        "needs_human_review": False,
    }
    return json.dumps(data, ensure_ascii=False)


async def classify_lead(
    payload: ClassifyRequest,
) -> Union[SuccessResponse, ErrorResponse]:
    settings = get_settings()
    request_id = str(uuid.uuid4())
    system_prompt = _load_prompt(f"system_{settings.PROMPT_VERSION}.txt")
    user_prompt = _build_user_prompt(payload)

    client = RouterAIClient()
    last_error: Optional[str] = None
    last_http_status: Optional[int] = None
    last_latency: Optional[float] = None
    last_tokens: Optional[dict] = None
    retries_done = 0

    for attempt in range(settings.MAX_RETRIES + 1):
        try:
            if settings.MOCK_LLM:
                content = _mock_response(payload)
                latency_ms = 10.0
                http_status = 200
                usage = None
            else:
                content, latency_ms, http_status, usage = await client.chat(
                    system_prompt, user_prompt
                )

            last_latency = latency_ms
            last_http_status = http_status
            last_tokens = usage

            # 1. Parse JSON
            try:
                raw_data = json.loads(content)
            except json.JSONDecodeError as e:
                last_error = f"Invalid JSON: {e}"
                if attempt < settings.MAX_RETRIES:
                    retries_done += 1
                    continue
                log_request(
                    request_id=request_id,
                    source=payload.source.value,
                    text=payload.text,
                    model=settings.MODEL_ID,
                    prompt_version=settings.PROMPT_VERSION,
                    schema_version=settings.SCHEMA_VERSION,
                    api_latency_ms=last_latency,
                    http_status=last_http_status,
                    retries=retries_done,
                    json_valid=False,
                    status="error",
                    error="LLM_RESPONSE_INVALID_JSON",
                    tokens=last_tokens,
                )
                return ErrorResponse(
                    request_id=request_id,
                    error=ErrorDetail(
                        code="LLM_RESPONSE_INVALID_JSON",
                        message="Модель вернула невалидный JSON.",
                    ),
                )

            # 2. JSON Schema validation
            try:
                jsonschema.validate(instance=raw_data, schema=LEAD_CARD_JSON_SCHEMA)
            except jsonschema.ValidationError as e:
                last_error = f"Schema validation failed: {e.message}"
                if attempt < settings.MAX_RETRIES:
                    retries_done += 1
                    continue
                log_request(
                    request_id=request_id,
                    source=payload.source.value,
                    text=payload.text,
                    model=settings.MODEL_ID,
                    prompt_version=settings.PROMPT_VERSION,
                    schema_version=settings.SCHEMA_VERSION,
                    api_latency_ms=last_latency,
                    http_status=last_http_status,
                    retries=retries_done,
                    json_valid=False,
                    status="error",
                    error="LLM_RESPONSE_VALIDATION_FAILED",
                    tokens=last_tokens,
                )
                return ErrorResponse(
                    request_id=request_id,
                    error=ErrorDetail(
                        code="LLM_RESPONSE_VALIDATION_FAILED",
                        message="Не удалось получить корректную структурированную карточку заявки.",
                    ),
                )

            # 3. Pydantic validation (extra safety)
            try:
                lead = LeadCard.model_validate(raw_data)
            except ValidationError as e:
                last_error = f"Pydantic validation failed: {e}"
                if attempt < settings.MAX_RETRIES:
                    retries_done += 1
                    continue
                log_request(
                    request_id=request_id,
                    source=payload.source.value,
                    text=payload.text,
                    model=settings.MODEL_ID,
                    prompt_version=settings.PROMPT_VERSION,
                    schema_version=settings.SCHEMA_VERSION,
                    api_latency_ms=last_latency,
                    http_status=last_http_status,
                    retries=retries_done,
                    json_valid=False,
                    status="error",
                    error="LLM_RESPONSE_VALIDATION_FAILED",
                    tokens=last_tokens,
                )
                return ErrorResponse(
                    request_id=request_id,
                    error=ErrorDetail(
                        code="LLM_RESPONSE_VALIDATION_FAILED",
                        message="Не удалось получить корректную структурированную карточку заявки.",
                    ),
                )

            # Success
            log_request(
                request_id=request_id,
                source=payload.source.value,
                text=payload.text,
                model=settings.MODEL_ID,
                prompt_version=settings.PROMPT_VERSION,
                schema_version=settings.SCHEMA_VERSION,
                api_latency_ms=last_latency,
                http_status=last_http_status,
                retries=retries_done,
                json_valid=True,
                status="success",
                tokens=last_tokens,
            )
            return SuccessResponse(
                request_id=request_id,
                model=settings.MODEL_ID,
                prompt_version=settings.PROMPT_VERSION,
                data=lead,
            )

        except RouterAIError as e:
            last_error = e.message
            last_http_status = e.http_status
            if attempt < settings.MAX_RETRIES and e.code in {
                "ROUTERAI_TIMEOUT",
                "ROUTERAI_UNAVAILABLE",
                "ROUTERAI_RATE_LIMIT",
            }:
                retries_done += 1
                continue

            log_request(
                request_id=request_id,
                source=payload.source.value,
                text=payload.text,
                model=settings.MODEL_ID,
                prompt_version=settings.PROMPT_VERSION,
                schema_version=settings.SCHEMA_VERSION,
                api_latency_ms=last_latency,
                http_status=last_http_status,
                retries=retries_done,
                json_valid=False,
                status="error",
                error=e.code,
                tokens=last_tokens,
            )
            return ErrorResponse(
                request_id=request_id,
                error=ErrorDetail(code=e.code, message=e.message),
            )

        except Exception as e:
            last_error = str(e)
            log_request(
                request_id=request_id,
                source=payload.source.value,
                text=payload.text,
                model=settings.MODEL_ID,
                prompt_version=settings.PROMPT_VERSION,
                schema_version=settings.SCHEMA_VERSION,
                api_latency_ms=last_latency,
                http_status=last_http_status,
                retries=retries_done,
                json_valid=False,
                status="error",
                error="INTERNAL_ERROR",
                tokens=last_tokens,
            )
            return ErrorResponse(
                request_id=request_id,
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Внутренняя ошибка сервиса.",
                ),
            )

    # Should not reach here
    return ErrorResponse(
        request_id=request_id,
        error=ErrorDetail(
            code="LLM_RESPONSE_VALIDATION_FAILED",
            message="Не удалось получить корректную структурированную карточку заявки.",
        ),
    )
