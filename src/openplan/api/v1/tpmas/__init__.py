import json
import logging
from typing import Annotated, Any

import azure.functions as func
from azure_functions_openapi import openapi
from packaging.version import Version
from pydantic import AfterValidator, BaseModel, Field, TypeAdapter

from openplan.api.v1.data import read_azure_json_file
from openplan.api.v1.handle_route_errors import handle_route_errors
from openplan.api.v1.models.version import VersionQuery
from openplan.api.v1.settings import CURRENT_APP_VERSION

bp = func.Blueprint()
logger = logging.getLogger(__name__)


def _get_TPMAs():
    return read_azure_json_file("api/tpmas.json")


def validate_tpma(value: str) -> str:
    if not is_valid_tpma(value):
        raise ValueError("Not recognised as a valid TPMA code")
    return value


TPMACode = Annotated[
    str,
    Field(
        pattern=r"^(IP|OP|AE)-(AA|EF)-\d{3}$",
        description="TPMA code.",
    ),
    AfterValidator(validate_tpma),
]


class TPMAPath(BaseModel):
    tpma: TPMACode


class TPMAResponseModel(BaseModel):
    model_config = {"extra": "allow"}


TPMAResponseSchema = TypeAdapter(dict[str, str]).json_schema()


def get_tpmas(version: Version | str | None = None) -> Any:
    if version is None or version == "dev":

        def compare_version(v):
            v2 = v.get("active_to")
            return v2 is None
    else:
        if isinstance(version, str):
            version = Version(version)

        def compare_version(v):
            v1 = v["active_from"]
            v2 = v.get("active_to")
            return Version(v1) <= version and (v2 is None or version < Version(v2))

    return {k: v for k, v in _get_TPMAs().items() if compare_version(v)}


def is_valid_tpma(tpma: str, version: Version | str | None = None) -> bool:
    return tpma in get_tpmas(version)


@bp.route("v1/tpmas", methods=["GET"])
@openapi(
    summary="List available TPMAs",
    description="Returns the TPMAs available for the requested API version.",
    tags=["TPMAs"],
    querystring=VersionQuery,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "schema": TPMAResponseSchema,
                }
            },
        },
        400: {"description": "Invalid request parameters"},
    },
)
@handle_route_errors
def route_tpmas(req: func.HttpRequest) -> func.HttpResponse:
    query_params = VersionQuery.model_validate(
        {"version": req.params.get("version", CURRENT_APP_VERSION)}
    )
    version = query_params.version

    tpmas = get_tpmas(version)
    return func.HttpResponse(json.dumps(tpmas), mimetype="application/json")
