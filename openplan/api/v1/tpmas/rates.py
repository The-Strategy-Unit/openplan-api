import logging
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query
import polars as pl

from openplan.api.v1.data import read_azure_parquet_file
from openplan.api.v1.error_handling import DATA_ERROR_RESPONSES
from openplan.api.v1.reference.providers import validate_provider
from openplan.api.v1.tpmas import TPMAIdentifier, validate_tpma
from openplan.api.v1.tpmas.models import Rate, RatesQuery

router = APIRouter(tags=["TPMA Rates"], responses=DATA_ERROR_RESPONSES)
logger = logging.getLogger(__name__)


def get_tpma_rates(
    version: str,
    tpma: str,
    provider: str | None = None,
    fyear: int | None = None,
) -> list[dict[str, Any]]:
    filename = f"api/{version}/provider/rates/{tpma}.parquet"
    frame = read_azure_parquet_file(filename)
    if provider is not None:
        frame = frame.filter(pl.col("provider") == provider)
    if fyear is not None:
        frame = frame.filter(pl.col("fyear") == fyear)
    return (
        frame.select("provider", "fyear", "denominator", "std_rate")
        .collect()
        .to_dicts()
    )


@router.get(
    "/v1/tpmas/{tpma}/rates", response_model=list[Rate],
    summary="Get TPMA rates",
    description=(
        "Returns rates for the specified TPMA, filtered by provider, financial year, "
        "or both. At least one of provider or fyear must be supplied. Each row "
        "contains provider, fyear, denominator, and std_rate."
    ),
)
def route_tpma_rates(
    tpma: Annotated[TPMAIdentifier, Path()],
    query: Annotated[RatesQuery, Query()],
) -> list[dict[str, Any]]:
    if query.provider is not None:
        validate_provider(query.provider, query.version)
    validate_tpma(tpma, query.version)
    logger.info(
        "Request for rates: version=%s, tpma=%s, provider=%s, fyear=%s",
        query.version, tpma, query.provider, query.fyear,
    )
    return get_tpma_rates(
        query.version, tpma, provider=query.provider,
        fyear=int(query.fyear) if query.fyear is not None else None,
    )
