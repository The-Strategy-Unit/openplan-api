from typing import Annotated

from fastapi import APIRouter, Query
from packaging.version import Version
from pydantic import Field

from openplan.api.v1.data import read_azure_json_file
from openplan.api.v1.error_handling import DATA_ERROR_RESPONSES, InvalidRequestParameters
from openplan.api.v1.models import VersionQuery

router = APIRouter(tags=["Reference"], responses=DATA_ERROR_RESPONSES)

ProviderIdentifier = Annotated[
    str,
    Field(
        min_length=3, max_length=5,
        pattern=r"^(?:[A-Z0-9]{3}|(?:[A-Z][0-9]){2}[A-Z])$",
        description="Provider ODS code.",
    ),
]


def _get_providers():
    return read_azure_json_file("api/providers.json")


def get_providers(version: Version | str | None = None) -> dict[str, str]:
    if version is None or version == "dev":
        def compare_version(record):
            return record.get("valid_to") is None
    else:
        if isinstance(version, str):
            version = Version(version)

        def compare_version(record):
            start = record["valid_from"]
            end = record.get("valid_to")
            return Version(start) <= version and (end is None or version < Version(end))
    return {code: record["name"] for code, record in _get_providers().items() if compare_version(record)}


def is_valid_provider(provider: str, version: Version | str | None = None) -> bool:
    return provider in get_providers(version)


def validate_provider(provider: str, version: str) -> str:
    if not is_valid_provider(provider, version):
        raise InvalidRequestParameters("provider", "Not recognised as a valid provider code")
    return provider


@router.get(
    "/v1/reference/providers", response_model=dict[str, str],
    summary="List available providers",
    description="Returns the providers available for the requested dataset version.",
)
def route_providers(query: Annotated[VersionQuery, Query()]) -> dict[str, str]:
    return get_providers(query.version)
