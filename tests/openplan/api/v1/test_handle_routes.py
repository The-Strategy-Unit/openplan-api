import json

import polars as pl
import pytest
from pydantic import BaseModel

from openplan.api.v1.handle_route_errors import (
    AzureError,
    ResourceNotFoundError,
    ServiceRequestError,
    ServiceResponseError,
    handle_route_errors,
)


def test_handle_route_errors_on_success():
    # arrange
    def route():
        return "success"

    # act
    result = handle_route_errors(route)()

    # assert
    assert result == "success"


def test_handle_route_errors_validation_error():
    # arrange

    def route():
        class MyModel(BaseModel):
            value: int

        MyModel(value="not an integer")

    # act
    actual = handle_route_errors(route)()

    # assert
    assert actual.status_code == 400
    assert json.loads(actual.get_body()) == {
        "error": "Invalid request parameters",
        "details": [
            {
                "field": "value",
                "message": "Input should be a valid integer, unable to parse string as an integer",
            }
        ],
    }


@pytest.mark.parametrize(
    "exception, status, message",
    [
        (ResourceNotFoundError, 404, "Dataset not found"),
        (ServiceRequestError, 503, "Data service temporarily unavailable"),
        (ServiceResponseError, 503, "Data service temporarily unavailable"),
        (AzureError, 500, "Data service error"),
        (pl.exceptions.PolarsError, 500, "Failed to process dataset"),
        (Exception, 500, "Internal server error"),
    ],
)
def test_handle_route_errors(exception, status, message):
    # arrange

    def route():
        raise exception("error")

    # act
    actual = handle_route_errors(route)()

    # assert
    assert actual.status_code == status
    assert json.loads(actual.get_body()) == {
        "error": message,
    }
