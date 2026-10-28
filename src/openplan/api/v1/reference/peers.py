import json
import logging
from typing import Any

import azure.functions as func
from azure_functions_openapi import openapi
from packaging.version import Version

from openplan.api.v1.data import read_azure_json_file
from openplan.api.v1.error_handling import handle_route_errors
from openplan.api.v1.models import VersionQuery
from openplan.api.v1.reference.providers import ProviderPath
from openplan.api.v1.settings import CURRENT_APP_VERSION

bp = func.Blueprint()
logger = logging.getLogger(__name__)


def _get_peers(provider: str, version: Version | str | None = None) -> Any:
    peers = read_azure_json_file("api/peers.json")

    if version is None or version == "dev":
        compare_version = lambda _: True
    else:
        if isinstance(version, str):
            version = Version(version)
        compare_version = lambda v: Version(v) <= version

    return max(
        (
            (Version(k2), v2)
            for k2, v2 in peers[provider].items()
            if compare_version(k2)
        ),
        default=(None, None),
        key=lambda x: x[0],
    )[1]


@bp.route("v1/reference/peers/{provider}", methods=["GET"])
@openapi(
    summary="List peer organisations for a provider",
    description="Returns the peer organisations available for the requested provider and version.",
    tags=["Reference"],
    path=ProviderPath,
    querystring=VersionQuery,
    responses={
        200: {
            "description": "Successful response",
            "content": {"application/json": {"schema": {"type": "object"}}},
        },
        400: {"description": "Invalid request parameters"},
    },
)
@handle_route_errors
def route_peers(req: func.HttpRequest) -> func.HttpResponse:
    path_params = ProviderPath.model_validate(
        {"provider": req.route_params.get("provider")}
    )
    provider = path_params.provider
    version = VersionQuery.model_validate(
        {"version": req.params.get("version", CURRENT_APP_VERSION)}
    ).version

    peers = _get_peers(provider, version)
    return func.HttpResponse(json.dumps(peers), mimetype="application/json")
