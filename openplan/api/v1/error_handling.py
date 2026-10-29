import logging
import re
from collections.abc import Callable
from functools import wraps
from typing import Any

import azure.functions as func
import polars as pl
from azure.core.exceptions import (
    AzureError,
    ResourceNotFoundError,
    ServiceRequestError,
    ServiceResponseError,
)
from pydantic import BaseModel, ValidationError


class ErrorResponse(BaseModel):
    error: str


class ParameterError(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(ErrorResponse):
    details: list[ParameterError]


DATA_ERROR_RESPONSES = {
    400: {
        "description": "Invalid request parameters",
        "content": {"application/json": {"schema": ValidationErrorResponse}},
    },
    404: {
        "description": "Resource or dataset not found",
        "content": {"application/json": {"schema": ErrorResponse}},
    },
    500: {
        "description": "The server could not read or process the dataset",
        "content": {"application/json": {"schema": ErrorResponse}},
    },
    503: {
        "description": "Data service temporarily unavailable",
        "content": {"application/json": {"schema": ErrorResponse}},
    },
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


def error_response(message: str, status_code: int) -> func.HttpResponse:
    return func.HttpResponse(
        ErrorResponse(error=message).model_dump_json(),
        status_code=status_code,
        mimetype="application/json",
    )


def validation_error_response(exc: ValidationError) -> func.HttpResponse:
    details = [
        {
            "field": ".".join(str(part) for part in err["loc"]),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    return func.HttpResponse(
        ValidationErrorResponse(
            error="Invalid request parameters", details=details,
        ).model_dump_json(),
        status_code=400,
        mimetype="application/json",
    )


def handle_route_errors(
    route: Callable[..., func.HttpResponse],
) -> Callable[..., func.HttpResponse]:
    @wraps(route)
    def wrapper(*args: Any, **kwargs: Any) -> func.HttpResponse:
        logger = logging.getLogger(route.__module__)
        try:
            return route(*args, **kwargs)

        except ValidationError as exc:
            logger.info("Invalid request parameters: %s", exc)
            return validation_error_response(exc)

        except ResourceNotFoundError:
            logger.info("Requested resource not found")
            return error_response("Dataset not found", 404)

        except (ServiceRequestError, ServiceResponseError):
            logger.exception("Azure Storage connection failed")
            return error_response("Data service temporarily unavailable", 503)

        except AzureError:
            logger.exception("Azure Storage request failed")
            return error_response("Data service error", 500)

        except pl.exceptions.PolarsError:
            logger.exception("Failed to process data")
            return error_response("Failed to process dataset", 500)

        except Exception:
            logger.exception("Unexpected route error")
            return error_response("Internal server error", 500)

    return wrapper
