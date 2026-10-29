import json
import logging
from typing import Any

import azure.functions as func
import polars as pl
from azure_functions_openapi import openapi

from openplan.api.v1.data import read_azure_parquet_file
from openplan.api.v1.error_handling import DATA_ERROR_RESPONSES, handle_route_errors
from openplan.api.v1.tpmas import TPMAPath
from openplan.api.v1.tpmas.models import RatesQuery, RatesResponseSchema

bp = func.Blueprint()
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


@bp.route(route="v1/tpmas/{tpma}/rates", methods=["GET"])
@openapi(
    summary="Get TPMA rates",
    description=(
        "Returns rates for the specified TPMA, filtered by provider, financial year, "
        "or both. At least one of provider or fyear must be supplied. Each row "
        "contains provider, fyear, denominator, and std_rate."
    ),
    tags=["TPMA Rates"],
    path=TPMAPath,
    querystring=RatesQuery,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "schema": RatesResponseSchema,
                }
            },
        },
        **DATA_ERROR_RESPONSES,
    },
)
@handle_route_errors
def route_tpma_rates(req: func.HttpRequest) -> func.HttpResponse:
    query_params = RatesQuery.model_validate(dict(req.params))
    tpma = TPMAPath.model_validate(
        {"tpma": req.route_params.get("tpma")},
        context={"version": query_params.version},
    ).tpma

    logger.info(
        "Request for rates: version=%s, tpma=%s, provider=%s, fyear=%s",
        query_params.version,
        tpma,
        query_params.provider,
        query_params.fyear,
    )

    rates = get_tpma_rates(
        query_params.version,
        tpma,
        provider=query_params.provider,
        fyear=int(query_params.fyear) if query_params.fyear is not None else None,
    )
    return func.HttpResponse(json.dumps(rates), mimetype="application/json")
