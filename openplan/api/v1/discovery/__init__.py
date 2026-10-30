from typing import TypeVar

import azure.functions as func
from azure_functions_openapi import openapi
from pydantic import BaseModel, ValidationError

from openplan.api.v1.data import read_azure_json_file_uncached
from openplan.api.v1.discovery.models import (
    DatasetIndex,
    DatasetManifest,
    DemographicAvailabilityResponse,
    RateAvailabilityResponse,
    VersionsResponse,
)
from openplan.api.v1.error_handling import error_response, handle_route_errors
from openplan.api.v1.models import VersionQuery
from openplan.api.v1.reference.providers import ProviderPath
from openplan.api.v1.tpmas import TPMAPath

bp = func.Blueprint()
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


@bp.route("v1/reference/versions", methods=["GET"])
@openapi(
    summary="List published dataset releases",
    description="Returns releases from the publisher's index, including publication time and source.",
    tags=["Discovery"],
    responses={200: VersionsResponse},
)
@handle_route_errors
def route_versions(req: func.HttpRequest) -> func.HttpResponse:
    index = _read_metadata("api/versions.json", DatasetIndex)
    return func.HttpResponse(
        VersionsResponse(versions=index.versions).model_dump_json(),
        mimetype="application/json", headers={"Cache-Control": "no-store"},
    )


@bp.route("v1/tpmas/{tpma}/rates/availability", methods=["GET"])
@openapi(
    summary="Get available TPMA rate selections",
    description="Lists valid provider and financial-year combinations for the selected dataset release.",
    tags=["Discovery"], path=TPMAPath, querystring=VersionQuery,
    responses={200: RateAvailabilityResponse},
)
@handle_route_errors
def route_rate_availability(req: func.HttpRequest) -> func.HttpResponse:
    version = VersionQuery.model_validate(dict(req.params)).version
    tpma = TPMAPath.model_validate(
        {"tpma": req.route_params.get("tpma")}, context={"version": version},
    ).tpma
    manifest = _read_manifest(version)
    dataset = manifest.rates.get(tpma)
    if dataset is None:
        return error_response("Rate availability not found for this TPMA and dataset version", 404)
    response = RateAvailabilityResponse(
        version=manifest.version, published_at=manifest.published_at,
        source=manifest.source, tpma=tpma, **dataset.model_dump(),
    )
    return func.HttpResponse(
        response.model_dump_json(), mimetype="application/json",
        headers={"Cache-Control": "no-store"},
    )


@bp.route("v1/providers/{provider}/demographic-factors/availability", methods=["GET"])
@openapi(
    summary="Get available demographic selections",
    description="Lists valid start-year, variant, and horizon-year combinations for both population and births.",
    tags=["Discovery"], path=ProviderPath, querystring=VersionQuery,
    responses={200: DemographicAvailabilityResponse},
)
@handle_route_errors
def route_demographic_availability(req: func.HttpRequest) -> func.HttpResponse:
    version = VersionQuery.model_validate(dict(req.params)).version
    provider = ProviderPath.model_validate(
        {"provider": req.route_params.get("provider")}, context={"version": version},
    ).provider
    manifest = _read_manifest(version)
    dataset = manifest.demographics.get(provider)
    if dataset is None:
        return error_response("Demographic availability not found for this provider and dataset version", 404)
    response = DemographicAvailabilityResponse(
        version=manifest.version, published_at=manifest.published_at,
        source=manifest.source, provider=provider, **dataset.model_dump(),
    )
    return func.HttpResponse(
        response.model_dump_json(), mimetype="application/json",
        headers={"Cache-Control": "no-store"},
    )
