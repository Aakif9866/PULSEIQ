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
from app.schemas.ai import AskRequest, AskResponse, AskSqlResponse
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse
from app.services.analyst_service import AnalystService
from app.services.deep_analysis_service import DeepAnalysisService
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


@router.post("/{dataset_id}/analyze", response_model=AnalyzeResponse)
def analyze_dataset(
    dataset_id: uuid.UUID,
    payload: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> AnalyzeResponse:
    """The hybrid AI Analyst (docs/AI_ANALYTICS.md) — a third, independent
    way to answer a question, alongside /ask and /ask-sql. Unlike those two
    single-shot endpoints, this one lets the model call analytical tools
    (app.ai.tool_specs) against the FULL dataset in a loop, gathering real
    evidence before producing a validated, evidence-cited answer. Same
    failure-mode-to-HTTP-status mapping as /ask and /ask-sql; a degraded
    (but still 200) AnalyzeResponse.status is used instead of an error when
    the AI service returns something unusable — the caller gets the exact
    required fallback message rather than a blank failure."""
    try:
        return DeepAnalysisService(db, storage).analyze(dataset_id, current_user.id, payload)
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


@router.post("/{dataset_id}/ask-sql", response_model=AskSqlResponse)
def ask_dataset_with_sql(
    dataset_id: uuid.UUID,
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageProvider = Depends(get_storage),
) -> AskSqlResponse:
    """Natural Language to SQL (docs/V2_ROADMAP.md) — a second, independent
    way to answer a question, alongside /ask. The AI generates SQL, which
    is validated (app.analytics.sql_validator) and executed via DuckDB
    (app.analytics.sql_engine) before anything is summarized — identical
    error handling to /ask, since the failure modes are the same shape."""
    try:
        return AnalystService(db, storage).ask_with_sql(
            dataset_id, current_user.id, payload.question
        )
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
            detail=f"Couldn't answer that question confidently: {exc}",
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
