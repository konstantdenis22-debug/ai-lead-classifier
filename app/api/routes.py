from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from app.schemas import ClassifyRequest, ErrorResponse, SuccessResponse
from app.services.classifier import classify_lead

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.post(
    "/classify",
    response_model=SuccessResponse | ErrorResponse,
    summary="Классификация клиентской заявки",
    description="Принимает текст заявки и возвращает структурированную карточку лида.",
)
async def classify(payload: ClassifyRequest) -> SuccessResponse | ErrorResponse:
    try:
        result = await classify_lead(payload)
        return result
    except ValidationError as e:
        # Should be caught by FastAPI, but just in case
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "VALIDATION_ERROR", "message": str(e)},
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": str(e)},
        ) from e
