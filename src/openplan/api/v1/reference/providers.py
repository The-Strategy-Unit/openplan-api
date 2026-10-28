import json
import logging
from typing import Annotated, Any

import azure.functions as func
from azure_functions_openapi import openapi
from packaging.version import Version
from pydantic import AfterValidator, BaseModel, Field, TypeAdapter, ValidationInfo

from openplan.api.v1.data import read_azure_json_file
from openplan.api.v1.error_handling import handle_route_errors
from openplan.api.v1.models import VersionQuery
from openplan.api.v1.settings import CURRENT_APP_VERSION

bp = func.Blueprint()
logger = logging.getLogger(__name__)


def _get_providers():
    return read_azure_json_file("api/providers.json")


def get_providers(version: Version | str | None = None) -> Any:
    if version is None or version == "dev":

        def compare_version(v):
            v2 = v.get("valid_to")
            return v2 is None
    else:
        if isinstance(version, str):
            version = Version(version)

        def compare_version(v):
            v1 = v["valid_from"]
            v2 = v.get("valid_to")
            return Version(v1) <= version and (v2 is None or version < Version(v2))

    return {k: v["name"] for k, v in _get_providers().items() if compare_version(v)}


def is_valid_provider(provider: str, version: Version | str | None = None) -> bool:
    return provider in get_providers(version)


def validate_provider(value: str, info: ValidationInfo | None = None) -> str:
    version = info.context if info else None

    if not is_valid_provider(value, version):
        raise ValueError("Not recognised as a valid provider code")
    return value


ProviderCode = Annotated[
    str,
    Field(
        min_length=3,
        max_length=5,
        pattern=r"^[A-Z0-9]{3}|([A-Z][0-9]){2}[A-Z]$",
        description="Provider ODS code.",
    ),
    AfterValidator(validate_provider),
]


class ProviderPath(BaseModel):
    provider: ProviderCode


@bp.route("v1/reference/providers", methods=["GET"])
@openapi(
    summary="List available providers",
    description="Returns the providers available for the requested API version.",
    tags=["Reference"],
    querystring=VersionQuery,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "schema": TypeAdapter(dict[str, str]).json_schema(),
                }
            },
        },
        400: {"description": "Invalid request parameters"},
    },
)
@handle_route_errors
def route_providers(req: func.HttpRequest) -> func.HttpResponse:
    query_params = VersionQuery.model_validate(
        {"version": req.params.get("version", CURRENT_APP_VERSION)}
    )
    version = query_params.version

    providers = get_providers(version)
    return func.HttpResponse(json.dumps(providers), mimetype="application/json")
