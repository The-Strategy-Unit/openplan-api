import json
import logging

import azure.functions as func
import polars as pl
from azure_functions_openapi import openapi
from pydantic import Field, field_validator

from openplan.api.v1.data import read_azure_csv_file
from openplan.api.v1.demographics.models import DemographicFactorsResponse
from openplan.api.v1.error_handling import DATA_ERROR_RESPONSES, handle_route_errors
from openplan.api.v1.models import VersionQuery
from openplan.api.v1.reference.providers import ProviderPath

bp = func.Blueprint()
logger = logging.getLogger(__name__)


class DemographicFactorsQuery(VersionQuery):
    start_year: int = Field(..., ge=1900, le=9999, description="Start year.")
    end_year: int = Field(..., ge=1900, le=9999, description="End year.")
    variant: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[^/\\]+$",
        description="Demographic variant identifier, without path separators.",
    )

    @field_validator("end_year")
    @classmethod
    def validate_end_year(cls, value: int, info) -> int:
        start_year = info.data.get("start_year")
        if start_year is not None and value < start_year:
            raise ValueError("end_year must be greater than or equal to start_year")
        return value


def get_demographic_factors(
    version: str,
    demog_type: str,
    fyear: int,
    provider: str,
    variant: str,
    start_year: int,
    end_year: int,
) -> dict[str, dict[int, dict[int, float]]]:
    filename = f"api/{version}/provider/demographics/{demog_type}/fyear={fyear}/provider={provider}/variant={variant}/part-0.csv"

    df = (
        read_azure_csv_file(filename)
        .select(
            pl.col("sex"),
            pl.col("age"),
            pl.col(str(start_year)).alias("baseline"),
            pl.col(str(end_year)).alias("horizon"),
        )
        .collect()
    )

    return {
        "baseline": {
            p["sex"][0]: dict(zip(p["age"], p["baseline"]))
            for p in df.partition_by("sex")
        },
        "horizon": {
            p["sex"][0]: dict(zip(p["age"], p["horizon"]))
            for p in df.partition_by("sex")
        },
    }


@bp.route(
    route="v1/providers/{provider}/demographic-factors",
    methods=["GET"],
)
@openapi(
    summary="Get demographic factors for a provider",
    description="Returns demographic factors for the specified provider and year range.",
    tags=["Demographics"],
    path=ProviderPath,
    querystring=DemographicFactorsQuery,
    responses={
        200: DemographicFactorsResponse,
        **DATA_ERROR_RESPONSES,
    },
)
@handle_route_errors
def route_demographic_factors(req: func.HttpRequest) -> func.HttpResponse:
    query_params = DemographicFactorsQuery.model_validate(dict(req.params))
    provider = ProviderPath.model_validate(
        {"provider": req.route_params.get("provider")},
        context={"version": query_params.version},
    ).provider
    version = query_params.version
    start_year = query_params.start_year
    end_year = query_params.end_year
    variant = query_params.variant

    logger.info(
        "Request for demographic factors: version=%s, provider=%s, start_year=%d, end_year=%d, variant=%s",
        version,
        provider,
        start_year,
        end_year,
        variant,
    )

    fyear = start_year * 100 + (start_year + 1) % 100

    demog_factors = {
        demog_type: get_demographic_factors(
            version,
            demog_type,
            fyear,
            provider,
            variant,
            start_year,
            end_year,
        )
        for demog_type in ["population", "births"]
    }

    return func.HttpResponse(json.dumps(demog_factors), mimetype="application/json")
