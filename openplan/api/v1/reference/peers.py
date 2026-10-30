from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from packaging.version import Version
from pydantic import JsonValue

from openplan.api.v1.data import read_azure_json_file
from openplan.api.v1.error_handling import DATA_ERROR_RESPONSES
from openplan.api.v1.models import VersionQuery
from openplan.api.v1.reference.providers import ProviderIdentifier, validate_provider

router = APIRouter(tags=["Reference"], responses=DATA_ERROR_RESPONSES)


def _get_peers(provider: str, version: Version | str | None = None) -> JsonValue:
    peers = read_azure_json_file("api/peers.json")
    if version is None or version == "dev":
        compare_version = lambda _: True
    else:
        if isinstance(version, str):
            version = Version(version)
        compare_version = lambda value: Version(value) <= version
    return max(
        ((Version(release), value) for release, value in peers.get(provider, {}).items() if compare_version(release)),
        default=(None, None), key=lambda item: item[0],
    )[1]


@router.get(
    "/v1/reference/peers/{provider}", response_model=JsonValue,
    summary="List peer organisations for a provider",
    description="Returns the publisher-defined JSON peer set for the requested provider and dataset version.",
)
def route_peers(
    provider: Annotated[ProviderIdentifier, Path()],
    query: Annotated[VersionQuery, Query()],
) -> JsonValue:
    validate_provider(provider, query.version)
    peers = _get_peers(provider, query.version)
    if peers is None:
        raise HTTPException(404, "No peer set available for this provider and dataset version")
    return peers
