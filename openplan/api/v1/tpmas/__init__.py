from typing import Annotated, Any

from fastapi import APIRouter, Query
from packaging.version import Version
from pydantic import BaseModel, Field

from openplan.api.v1.data import read_azure_json_file
from openplan.api.v1.error_handling import DATA_ERROR_RESPONSES, InvalidRequestParameters
from openplan.api.v1.models import VersionQuery

router = APIRouter(tags=["TPMAs"], responses=DATA_ERROR_RESPONSES)

TPMAIdentifier = Annotated[str, Field(pattern=r"^(IP|OP|AE)-(AA|EF)-\d{3}$", description="TPMA code.")]


class TPMAResponseModel(BaseModel):
    model_config = {"extra": "allow"}
    active_from: str
    active_to: str | None = None


def _get_TPMAs():
    return read_azure_json_file("api/tpmas.json")


def get_tpmas(version: Version | str | None = None) -> dict[str, Any]:
    if version is None or version == "dev":
        def compare_version(record):
            return record.get("active_to") is None
    else:
        if isinstance(version, str):
            version = Version(version)

        def compare_version(record):
            start = record["active_from"]
            end = record.get("active_to")
            return Version(start) <= version and (end is None or version < Version(end))
    return {code: record for code, record in _get_TPMAs().items() if compare_version(record)}


def is_valid_tpma(tpma: str, version: Version | str | None = None) -> bool:
    return tpma in get_tpmas(version)


def validate_tpma(tpma: str, version: str) -> str:
    if not is_valid_tpma(tpma, version):
        raise InvalidRequestParameters("tpma", "Not recognised as a valid TPMA code")
    return tpma


@router.get(
    "/v1/tpmas", response_model=dict[str, TPMAResponseModel], response_model_exclude_unset=True,
    summary="List available TPMAs",
    description="Returns the TPMAs available for the requested dataset version.",
)
def route_tpmas(query: Annotated[VersionQuery, Query()]) -> dict[str, Any]:
    return get_tpmas(query.version)
