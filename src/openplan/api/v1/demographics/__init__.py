import json
import logging

import azure.functions as func
import polars as pl
from azure_functions_openapi import openapi
from pydantic import BaseModel, Field, field_validator

from openplan.api.v1.data import read_azure_csv_file
from openplan.api.v1.handle_route_errors import handle_route_errors
from openplan.api.v1.models.version import VersionQuery
from openplan.api.v1.reference.providers import ProviderCode
from openplan.api.v1.settings import CURRENT_APP_VERSION

bp = func.Blueprint()
logger = logging.getLogger(__name__)


class DemographicFactorsPath(BaseModel):
    provider: ProviderCode
    start_year: int = Field(..., ge=1900, le=9999, description="Start year.")
    end_year: int = Field(..., ge=1900, le=9999, description="End year.")
    variant: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Demographic variant identifier.",
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
    route="v1/demographics/provider/{provider}/{start_year}/{end_year}/{variant}",
    methods=["GET"],
)
@openapi(
    summary="Get demographic factors for a provider",
    description="Returns demographic factors for the specified provider and year range.",
    tags=["Demographics"],
    path=DemographicFactorsPath,
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
def route_demographic_factors(req: func.HttpRequest) -> func.HttpResponse:
    version = VersionQuery.model_validate(
        {"version": req.params.get("version", CURRENT_APP_VERSION)}
    ).version
    route_params = DemographicFactorsPath.model_validate(
        {
            "provider": req.route_params.get("provider"),
            "start_year": req.route_params.get("start_year"),
            "end_year": req.route_params.get("end_year"),
            "variant": req.route_params.get("variant"),
        }
    )
    provider = route_params.provider
    start_year = route_params.start_year
    end_year = route_params.end_year
    variant = route_params.variant

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
