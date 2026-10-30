import logging
from typing import Annotated

from fastapi import APIRouter, Path, Query
import polars as pl
from pydantic import Field, field_validator

from openplan.api.v1.data import read_azure_csv_file
from openplan.api.v1.demographics.models import DemographicFactorsResponse
from openplan.api.v1.error_handling import DATA_ERROR_RESPONSES
from openplan.api.v1.models import VersionQuery
from openplan.api.v1.reference.providers import ProviderIdentifier, validate_provider

router = APIRouter(tags=["Demographics"], responses=DATA_ERROR_RESPONSES)
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


@router.get(
    "/v1/providers/{provider}/demographic-factors",
    response_model=DemographicFactorsResponse,
    summary="Get demographic factors for a provider",
    description="Returns demographic factors for the specified provider and year range.",
)
def route_demographic_factors(
    provider: Annotated[ProviderIdentifier, Path()],
    query: Annotated[DemographicFactorsQuery, Query()],
) -> DemographicFactorsResponse:
    validate_provider(provider, query.version)
    logger.info(
        "Request for demographic factors: version=%s, provider=%s, start_year=%d, end_year=%d, variant=%s",
        query.version, provider, query.start_year, query.end_year, query.variant,
    )
    fyear = query.start_year * 100 + (query.start_year + 1) % 100
    factors = {
        kind: get_demographic_factors(
            query.version, kind, fyear, provider, query.variant, query.start_year, query.end_year,
        )
        for kind in ("population", "births")
    }
    return DemographicFactorsResponse(**factors)
