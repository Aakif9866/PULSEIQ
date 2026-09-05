from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware

configure_logging(debug=settings.DEBUG)
logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered self-service analytics platform.",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
)

# Order matters: middleware runs outside-in on the way in, inside-out on the
# way out. CORS added last so it wraps everything, including error responses.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
def handle_domain_error(_request: Request, exc: DomainError) -> JSONResponse:
    # Fallback for any DomainError not translated to an HTTPException at the
    # route layer — never leak internals, log the real exception server-side.
    logger.warning("unhandled_domain_error", error_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "The request could not be completed."},
    )


@app.exception_handler(Exception)
def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error_type=type(exc).__name__, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Something went wrong on our end. Please try again."},
    )


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.APP_NAME, "status": "running"}
