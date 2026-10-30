from typing import Annotated, TypeVar

from fastapi import APIRouter, HTTPException, Path, Query, Response
from pydantic import BaseModel, ValidationError

from openplan.api.v1.data import read_azure_json_file_uncached
from openplan.api.v1.discovery.models import (
    DatasetIndex, DatasetManifest, DemographicAvailabilityResponse,
    RateAvailabilityResponse, VersionsResponse,
)
from openplan.api.v1.error_handling import DATA_ERROR_RESPONSES, METADATA_ERROR_RESPONSES
from openplan.api.v1.models import VersionQuery
from openplan.api.v1.reference.providers import ProviderIdentifier, validate_provider
from openplan.api.v1.tpmas import TPMAIdentifier, validate_tpma

router = APIRouter(tags=["Discovery"])
Metadata = TypeVar("Metadata", bound=BaseModel)


def _read_metadata(filename: str, model: type[Metadata]) -> Metadata:
    try:
        return model.model_validate(read_azure_json_file_uncached(filename))
    except ValidationError as exc:
        # Published metadata failures are server errors, not invalid requests.
        raise ValueError("Invalid published dataset metadata") from exc


def _read_manifest(version: str) -> DatasetManifest:
    manifest = _read_metadata(f"api/{version}/manifest.json", DatasetManifest)
    if manifest.version != version:
        raise ValueError("Dataset manifest does not match the requested version")
    return manifest


@router.get(
    "/v1/reference/versions", response_model=VersionsResponse,
    summary="List published dataset releases",
    description="Returns releases from the publisher's index, including publication time and source.",
    responses=METADATA_ERROR_RESPONSES,
)
def route_versions(response: Response) -> VersionsResponse:
    index = _read_metadata("api/versions.json", DatasetIndex)
    response.headers["Cache-Control"] = "no-store"
    return VersionsResponse(versions=index.versions)


@router.get(
    "/v1/tpmas/{tpma}/rates/availability", response_model=RateAvailabilityResponse,
    summary="Get available TPMA rate selections",
    description="Lists valid provider and financial-year combinations for the selected dataset release.",
    responses=DATA_ERROR_RESPONSES,
)
def route_rate_availability(
    tpma: Annotated[TPMAIdentifier, Path()],
    query: Annotated[VersionQuery, Query()],
    response: Response,
) -> RateAvailabilityResponse:
    validate_tpma(tpma, query.version)
    manifest = _read_manifest(query.version)
    dataset = manifest.rates.get(tpma)
    if dataset is None:
        raise HTTPException(404, "Rate availability not found for this TPMA and dataset version")
    response.headers["Cache-Control"] = "no-store"
    return RateAvailabilityResponse(
        version=manifest.version, published_at=manifest.published_at,
        source=manifest.source, tpma=tpma, **dataset.model_dump(),
    )


@router.get(
    "/v1/providers/{provider}/demographic-factors/availability",
    response_model=DemographicAvailabilityResponse,
    summary="Get available demographic selections",
    description="Lists valid start-year, variant, and horizon-year combinations for both population and births.",
    responses=DATA_ERROR_RESPONSES,
)
def route_demographic_availability(
    provider: Annotated[ProviderIdentifier, Path()],
    query: Annotated[VersionQuery, Query()],
    response: Response,
) -> DemographicAvailabilityResponse:
    validate_provider(provider, query.version)
    manifest = _read_manifest(query.version)
    dataset = manifest.demographics.get(provider)
    if dataset is None:
        raise HTTPException(404, "Demographic availability not found for this provider and dataset version")
    response.headers["Cache-Control"] = "no-store"
    return DemographicAvailabilityResponse(
        version=manifest.version, published_at=manifest.published_at,
        source=manifest.source, provider=provider, **dataset.model_dump(),
    )
