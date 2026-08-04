# AI-классификатор клиентских заявок

Сервис автоматической обработки входящих заявок на разработку сайтов, веб-сервисов, Telegram-ботов, AI-автоматизацию, интеграции и другие digital-услуги.

Использует **Grok 4.20** от xAI через **RouterAI**. Возвращает структурированную карточку лида в формате JSON.

---

## Возможности

- Приём заявки через `POST /api/leads/classify`
- Классификация услуги, типа проекта, бюджета, сроков, качества лида
- Строгая защита от галлюцинаций (модель не придумывает данные)
- Валидация ответа по JSON Schema + Pydantic
- Автоматический повтор при невалидном ответе
- Полное техническое логирование
- Набор из 28+ тестовых кейсов + автоматический runner
- Обработка ошибок RouterAI (auth, rate-limit, timeout и др.)

---

## Быстрый старт

### 1. Клонирование и установка

```bash
git clone <your-repo-url>
cd ai-lead-classifier

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env и укажите ROUTERAI_API_KEY
```

Получить ключ: [https://routerai.ru](https://routerai.ru) → Настройки → API-ключи.

Подтвердите точный идентификатор модели в личном кабинете RouterAI (по умолчанию `x-ai/grok-4.20`).

### 3. Запуск сервиса

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Документация: http://localhost:8000/docs

### 4. Пример запроса

```bash
curl -X POST http://localhost:8000/api/leads/classify \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Добрый день. Нужен сайт для автосервиса: услуги, онлайн-запись, карта и отзывы. Бюджет около 200 тыс. руб. Хотим запуститься до сентября.",
    "source": "telegram",
    "received_at": "2026-08-03T10:00:00+03:00",
    "known_client_name": null,
    "known_contact": null,
    "language": "ru"
  }'
```

### 5. Запуск тестов

```bash
# С реальным API (нужен ключ)
python tests/test_runner.py

# Или через pytest
pytest tests/ -v
```

Отчёт сохраняется в `reports/test_report_*.json`.

---

## Структура проекта

```
ai-lead-classifier/
├── app/
│   ├── main.py                 # FastAPI приложение
│   ├── config.py               # Настройки из .env
│   ├── schemas.py              # Pydantic + JSON Schema
│   ├── prompts/
│   │   ├── system_v1.0.0.txt   # Системный промпт
│   │   └── user_template.txt   # Шаблон пользовательского промпта
│   ├── services/
│   │   ├── classifier.py       # Основная логика
│   │   ├── routerai.py         # Клиент RouterAI
│   │   └── logger.py           # Структурированные логи
│   └── api/
│       └── routes.py           # Endpoint
├── tests/
│   ├── test_cases.json         # ≥25 тестовых заявок
│   └── test_runner.py          # Автоматический runner + отчёт
├── logs/                       # Технические логи (jsonl)
├── reports/                    # Отчёты тестов
├── .env.example
├── requirements.txt
└── README.md
```

---

## Формат ответа (успех)

```json
{
  "success": true,
  "request_id": "uuid",
  "model": "x-ai/grok-4.20",
  "prompt_version": "v1.0.0",
  "data": {
    "request_summary": "...",
    "service": "Корпоративный сайт",
    "industry": "Автосервис",
    "project_type": "Новый проект",
    "required_features": ["Раздел услуг", "Форма онлайн-записи", "..."],
    "integrations": [],
    "budget_min_rub": 200000,
    "budget_max_rub": 200000,
    "deadline_text": "до сентября",
    "deadline_date": null,
    "urgency": "средняя",
    "client_name": null,
    "company_name": null,
    "contact": "Telegram",
    "contact_value": null,
    "lead_quality": "горячий",
    "missing_questions": ["..."],
    "confidence": 0.91,
    "needs_human_review": false
  }
}
```

## Формат ответа (ошибка)

```json
{
  "success": false,
  "request_id": "uuid",
  "error": {
    "code": "LLM_RESPONSE_VALIDATION_FAILED",
    "message": "Не удалось получить корректную структурированную карточку заявки."
  }
}
```

Поддерживаемые коды ошибок:  
`VALIDATION_ERROR`, `ROUTERAI_AUTH_ERROR`, `ROUTERAI_RATE_LIMIT`, `ROUTERAI_TIMEOUT`, `ROUTERAI_UNAVAILABLE`, `LLM_RESPONSE_INVALID_JSON`, `LLM_RESPONSE_VALIDATION_FAILED`, `INTERNAL_ERROR`.

---

## Логирование

Каждый запрос записывается в `logs/processing.jsonl` со следующими полями:

- `request_id`
- `processed_at`
- `source`
- `text` (обрезанный)
- `model`
- `prompt_version`
- `schema_version`
- `api_latency_ms`
- `http_status`
- `retries`
- `json_valid`
- `status` (`success` / `error`)
- `error`
- `tokens` (если доступны)

API-ключ и секреты **никогда** не логируются.

---

## Критерии приёмки (автоматически проверяются)

| Критерий                    | Требование                          |
|----------------------------|-------------------------------------|
| Модель                     | Grok 4.20 через RouterAI            |
| JSON-валидность            | 100%                                |
| Классификация услуги       | ≥ 85%                               |
| Извлечение бюджета         | ≥ 90% (если указан явно)            |
| Извлечение сроков          | ≥ 85% (если однозначно)             |
| Выдуманные данные          | ≤ 1 случай на 25 тестов             |
| Повторяемость              | Ключевые поля стабильны             |
| Ошибки                     | Корректная обработка всех кодов     |
| Безопасность               | Ключ не в репозитории и логах       |

---

## Версии

- **Промпт**: `v1.0.0`
- **JSON Schema**: `v1.0.0`
- **Сервис**: `1.0.0`

---

## Лицензия

Учебный проект. Используйте свободно в рамках задания.
