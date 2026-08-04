from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import router
from app.schemas import ErrorDetail, ErrorResponse

app = FastAPI(
    title="AI Lead Classifier",
    description="Сервис автоматической классификации клиентских заявок на digital-услуги с помощью Grok 4.20 через RouterAI.",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            request_id="validation-error",
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Ошибка валидации входных данных: " + str(exc.errors()),
            ),
        ).model_dump(),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


@app.get("/")
async def root():
    return {
        "service": "AI Lead Classifier",
        "version": __version__,
        "docs": "/docs",
        "endpoint": "POST /api/leads/classify",
    }
