from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, confloat, field_validator


# ---------------------------------------------------------------------------
# Allowed values (from ТЗ §7)
# ---------------------------------------------------------------------------

class ServiceType(str, Enum):
    LANDING = "Лендинг"
    CORPORATE = "Корпоративный сайт"
    ECOM = "Интернет-магазин"
    WEB_SERVICE = "Веб-сервис"
    TELEGRAM_BOT = "Telegram-бот"
    MOBILE = "Мобильное приложение"
    PARSER = "Парсер / сбор данных"
    AI_AUTO = "AI-автоматизация"
    CRM = "CRM / бизнес-автоматизация"
    API_INTEGRATION = "Интеграция API"
    SUPPORT = "Поддержка / доработка"
    CONSULT = "Консультация"
    OTHER = "Другое"
    UNDEFINED = "Не определено"


class ProjectType(str, Enum):
    NEW = "Новый проект"
    IMPROVE = "Доработка существующего проекта"
    REDESIGN = "Редизайн"
    SUPPORT = "Поддержка"
    CONSULT = "Консультация"
    UNDEFINED = "Не определено"


class Urgency(str, Enum):
    LOW = "низкая"
    MEDIUM = "средняя"
    HIGH = "высокая"
    UNDEFINED = "не определено"


class LeadQuality(str, Enum):
    HOT = "горячий"
    WARM = "тёплый"
    COLD = "холодный"
    UNDEFINED = "не определено"


class ContactChannel(str, Enum):
    TELEGRAM = "Telegram"
    WHATSAPP = "WhatsApp"
    EMAIL = "Email"
    PHONE = "Телефон"
    SITE = "Сайт"
    OTHER = "Другое"


class SourceType(str, Enum):
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    WEBSITE_FORM = "website_form"
    EMAIL = "email"
    CRM = "crm"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Полный текст заявки клиента")
    source: SourceType = Field(..., description="Источник заявки")
    received_at: str = Field(..., description="Дата и время получения в ISO 8601")
    known_client_name: Optional[str] = Field(None, description="Имя клиента, если известно")
    known_contact: Optional[str] = Field(None, description="Контакт клиента, если известен")
    language: Optional[str] = Field("ru", description="Язык заявки (ru / en)")

    @field_validator("received_at")
    @classmethod
    def validate_iso_datetime(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError("received_at must be a valid ISO 8601 datetime") from e
        return v


# ---------------------------------------------------------------------------
# Lead Card (response data)
# ---------------------------------------------------------------------------

class LeadCard(BaseModel):
    request_summary: str = Field(..., description="Краткое описание задачи в 1–2 предложениях")
    service: ServiceType
    industry: Optional[str] = None
    project_type: ProjectType
    required_features: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    budget_min_rub: Optional[float] = None
    budget_max_rub: Optional[float] = None
    deadline_text: Optional[str] = None
    deadline_date: Optional[str] = Field(None, description="YYYY-MM-DD or null")
    urgency: Urgency
    client_name: Optional[str] = None
    company_name: Optional[str] = None
    contact: Optional[ContactChannel] = None
    contact_value: Optional[str] = None
    lead_quality: LeadQuality
    missing_questions: list[str] = Field(default_factory=list)
    confidence: confloat(ge=0.0, le=1.0)
    needs_human_review: bool = False

    @field_validator("deadline_date")
    @classmethod
    def validate_deadline_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError("deadline_date must be YYYY-MM-DD or null") from e
        return v


# ---------------------------------------------------------------------------
# API Responses
# ---------------------------------------------------------------------------

class SuccessResponse(BaseModel):
    success: bool = True
    request_id: str
    model: str
    prompt_version: str
    data: LeadCard


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    request_id: str
    error: ErrorDetail


# ---------------------------------------------------------------------------
# JSON Schema for LLM (exported for prompt & validation)
# ---------------------------------------------------------------------------

LEAD_CARD_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "LeadCard",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "request_summary",
        "service",
        "project_type",
        "required_features",
        "integrations",
        "urgency",
        "lead_quality",
        "missing_questions",
        "confidence",
        "needs_human_review",
    ],
    "properties": {
        "request_summary": {"type": "string", "minLength": 1},
        "service": {
            "type": "string",
            "enum": [e.value for e in ServiceType],
        },
        "industry": {"type": ["string", "null"]},
        "project_type": {
            "type": "string",
            "enum": [e.value for e in ProjectType],
        },
        "required_features": {
            "type": "array",
            "items": {"type": "string"},
        },
        "integrations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "budget_min_rub": {"type": ["number", "null"]},
        "budget_max_rub": {"type": ["number", "null"]},
        "deadline_text": {"type": ["string", "null"]},
        "deadline_date": {
            "type": ["string", "null"],
            "pattern": r"^(\d{4}-\d{2}-\d{2})?$",
        },
        "urgency": {
            "type": "string",
            "enum": [e.value for e in Urgency],
        },
        "client_name": {"type": ["string", "null"]},
        "company_name": {"type": ["string", "null"]},
        "contact": {
            "type": ["string", "null"],
            "enum": [e.value for e in ContactChannel] + [None],
        },
        "contact_value": {"type": ["string", "null"]},
        "lead_quality": {
            "type": "string",
            "enum": [e.value for e in LeadQuality],
        },
        "missing_questions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "needs_human_review": {"type": "boolean"},
    },
}
