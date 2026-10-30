import logging
import re

import polars as pl
from azure.core.exceptions import AzureError, ResourceNotFoundError, ServiceRequestError, ServiceResponseError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException


class ErrorResponse(BaseModel):
    error: str


class ParameterError(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(ErrorResponse):
    details: list[ParameterError]


class InvalidRequestParameters(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.details = [ParameterError(field=field, message=message)]


DATA_ERROR_RESPONSES = {
    400: {"description": "Invalid request parameters", "model": ValidationErrorResponse},
    404: {"description": "Resource or dataset not found", "model": ErrorResponse},
    500: {"description": "The server could not read or process the dataset", "model": ErrorResponse},
    503: {"description": "Data service temporarily unavailable", "model": ErrorResponse},
}
METADATA_ERROR_RESPONSES = {
    status: DATA_ERROR_RESPONSES[status] for status in (404, 500, 503)
}


def is_valid_fyear(fyear: str) -> bool:
    if re.fullmatch(r"[0-9]{6}", fyear) is None:
        return False
    start_year = int(fyear[:4])
    return start_year > 0 and int(fyear[4:]) == (start_year + 1) % 100


def is_valid_version(version: str) -> bool:
    return bool(re.match(r"^(dev|v\d+\.\d+(\.\d+)?)$", version))


def error_response(message: str, status_code: int, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        ErrorResponse(error=message).model_dump(mode="json"),
        status_code=status_code, headers=headers,
    )


def _validation_response(details: list[ParameterError]) -> JSONResponse:
    return JSONResponse(
        ValidationErrorResponse(error="Invalid request parameters", details=details).model_dump(mode="json"),
        status_code=400,
    )


async def _handle_error(request: Request, exc: Exception) -> JSONResponse:
    endpoint = request.scope.get("endpoint")
    logger = logging.getLogger(getattr(endpoint, "__module__", __name__))
    if isinstance(exc, RequestValidationError):
        details = []
        for error in exc.errors():
            location = error["loc"]
            if location and location[0] in ("query", "path", "body", "header", "cookie"):
                location = location[1:]
            details.append(ParameterError(
                field=".".join(str(part) for part in location), message=error["msg"],
            ))
        logger.info("Invalid request parameters")
        return _validation_response(details)
    if isinstance(exc, InvalidRequestParameters):
        logger.info("Invalid request parameters: %s", exc)
        return _validation_response(exc.details)
    if isinstance(exc, HTTPException):
        return error_response(str(exc.detail), exc.status_code, exc.headers)
    if isinstance(exc, ResourceNotFoundError):
        logger.info("Requested resource not found")
        return error_response("Dataset not found", 404)
    if isinstance(exc, (ServiceRequestError, ServiceResponseError)):
        status, message = 503, "Data service temporarily unavailable"
    elif isinstance(exc, AzureError):
        status, message = 500, "Data service error"
    elif isinstance(exc, pl.exceptions.PolarsError):
        status, message = 500, "Failed to process dataset"
    else:
        status, message = 500, "Internal server error"
    logger.error(message, exc_info=(type(exc), exc, exc.__traceback__))
    return error_response(message, status)


def register_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def handle_unexpected_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            # Starlette's outer server-error handler re-raises after sending.
            # Catch here so Azure's ASGI adapter can return the JSON response.
            return await _handle_error(request, exc)

    for error_type in (
        RequestValidationError, InvalidRequestParameters, HTTPException,
        ResourceNotFoundError, ServiceRequestError, ServiceResponseError,
        AzureError, pl.exceptions.PolarsError,
    ):
        app.add_exception_handler(error_type, _handle_error)
