"""API error handling conventions."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from rl_trade_api.schemas.errors import ErrorResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
        payload = ErrorResponse(
            error="http_error",
            message=str(exc.detail),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(_: Request, exc: RequestValidationError) -> JSONResponse:
        payload = ErrorResponse(
            error="validation_error",
            message="Request validation failed.",
            details=exc.errors(),
        )
        return JSONResponse(status_code=422, content=payload.model_dump())
