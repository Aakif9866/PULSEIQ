import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage
from app.core.database import get_db
from app.core.exceptions import (
    AiNotConfiguredError,
    AiResponseError,
    ColumnNotFoundError,
    DatasetNotFoundError,
    DatasetNotReadyError,
    InvalidQueryError,
    QueryTimeoutError,
)
from app.models.user import User
from app.schemas.ai import AskRequest, AskResponse
from app.services.analyst_service import AnalystService
from app.storage import StorageProvider

router = APIRouter(prefix="/datasets", tags=["analysis"])


@router.post("/{dataset_id}/ask", response_model=AskResponse)
def ask_dataset(
    dataset_id: uuid.UUID,
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> AskResponse:
    try:
        return AnalystService(db, storage).ask(dataset_id, current_user.id, payload.question)
    except AiNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI analyst isn't configured yet.",
        ) from exc
    except DatasetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from exc
    except DatasetNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This dataset isn't ready to analyze yet (profiling hasn't succeeded).",
        ) from exc
    except (ColumnNotFoundError, InvalidQueryError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Couldn't answer that question confidently. Try rephrasing it.",
        ) from exc
    except QueryTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="That question took too long to analyze. Try narrowing it down.",
        ) from exc
    except AiResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc) or "The AI analyst is temporarily unavailable. Try again.",
        ) from exc
