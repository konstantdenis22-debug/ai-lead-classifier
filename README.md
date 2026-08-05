# AI-классификатор клиентских заявок

Сервис автоматической обработки входящих заявок на разработку сайтов, веб-сервисов, Telegram-ботов, AI-автоматизацию и другие digital-услуги.

Использует **Grok 4.20** от xAI через **RouterAI**. Возвращает структурированную карточку лида в формате JSON.

---

## Быстрый старт (с нуля)

### 1. Клонирование

```bash
git clone https://github.com/konstantdenis22-debug/ai-lead-classifier.git
cd ai-lead-classifier
```

### 2. Виртуальное окружение

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Если появляется ошибка про ExecutionPolicy:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**Mac / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка API-ключа (обязательно)

```bash
cp .env.example .env
```

Откройте файл `.env` и вставьте свой ключ:

```env
ROUTERAI_API_KEY=ваш_реальный_ключ_от_преподавателя
```

Без ключа сервис вернёт ошибку `ROUTERAI_AUTH_ERROR` в стандартизированном формате.

### 5. Запуск

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Откройте в браузере: http://127.0.0.1:8000/docs

### 6. Запуск тестов

```bash
python tests/test_runner.py
```

Отчёт появится в папке `reports/` (файлы `latest_report.json` и `test_report_*.json`).

---

## Пример запроса

```bash
curl -X POST http://127.0.0.1:8000/api/leads/classify \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"Добрый день. Нужен сайт для автосервиса: услуги, онлайн-запись, карта и отзывы. Бюджет около 200 тыс. руб. Хотим запуститься до сентября.\",
    \"source\": \"telegram\",
    \"received_at\": \"2026-08-03T10:00:00+03:00\",
    \"known_client_name\": null,
    \"known_contact\": null,
    \"language\": \"ru\"
  }"
```

---

## Структура проекта

```
ai-lead-classifier/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── schemas.py              # Pydantic + JSON Schema
│   ├── prompts/
│   │   ├── system_v1.0.0.txt
│   │   └── user_template.txt
│   ├── services/
│   │   ├── classifier.py
│   │   ├── routerai.py
│   │   └── logger.py
│   └── api/routes.py
├── tests/
│   ├── test_cases.json         # 28 кейсов
│   └── test_runner.py          # Честный автоматический runner
├── reports/                    # Сюда пишутся отчёты
├── docs/
│   └── example_success_response.json
├── .env.example
├── requirements.txt
├── CHANGES.md
└── README.md
```

---

## Формат ошибок (единый)

При любой ошибке (нет ключа, невалидный JSON, проблемы RouterAI и т.д.) возвращается:

```json
{
  "success": false,
  "request_id": "uuid",
  "error": {
    "code": "ROUTERAI_AUTH_ERROR",
    "message": "..."
  }
}
```

Поддерживаемые коды:  
`VALIDATION_ERROR`, `ROUTERAI_AUTH_ERROR`, `ROUTERAI_RATE_LIMIT`, `ROUTERAI_TIMEOUT`, `ROUTERAI_UNAVAILABLE`, `LLM_RESPONSE_INVALID_JSON`, `LLM_RESPONSE_VALIDATION_FAILED`, `INTERNAL_ERROR`.

---

## Повторяемость

В `tests/test_runner.py` есть проверка повторяемости: выбранные кейсы (TC-001, TC-002, TC-010) запускаются 3 раза. Результат записывается в отчёт в поле `repeatability`.

---

## Что сдаётся (п. 15 ТЗ)

- Ссылка на GitHub-репозиторий
- Исходный код
- `.env.example`
- `README.md`
- Системный промпт и шаблон пользовательского промпта
- JSON Schema (в `app/schemas.py`)
- Тестовый набор (28 кейсов)
- Модуль автоматического тестирования
- Отчёт по тестам (`reports/latest_report.json`)
- Пример успешного ответа (`docs/example_success_response.json`)
- Описание логов (в этом README и в коде логгера)

---

## Лицензия

Учебный проект.
