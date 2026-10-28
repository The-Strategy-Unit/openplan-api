import json
import logging
from typing import Any

import azure.functions as func
import polars as pl
from azure_functions_openapi import openapi

from openplan.api.v1.data import read_azure_parquet_file
from openplan.api.v1.handle_route_errors import handle_route_errors
from openplan.api.v1.models.fyear import FinancialYearPath
from openplan.api.v1.models.version import VersionQuery
from openplan.api.v1.reference.providers import ProviderPath
from openplan.api.v1.settings import CURRENT_APP_VERSION
from openplan.api.v1.tpmas import TPMAPath
from openplan.api.v1.tpmas.models import RatesByFyear, RatesByProvider

bp = func.Blueprint()
logger = logging.getLogger(__name__)


def get_tpma_rates_for_provider(
    version: str,
    provider: str,
    tpma: str,
) -> list[dict[str, Any]]:
    filename = f"api/{version}/provider/rates/{tpma}.parquet"
    return (
        read_azure_parquet_file(filename)
        .filter(pl.col("provider") == provider)
        .select(pl.col("fyear"), pl.col("denominator"), pl.col("std_rate"))
        .collect()
        .to_dicts()
    )


def get_tpma_rates_for_fyear(
    version: str,
    fyear: int,
    tpma: str,
) -> list[dict[str, Any]]:
    filename = f"api/{version}/provider/rates/{tpma}.parquet"
    return (
        read_azure_parquet_file(filename)
        .filter(pl.col("fyear") == fyear)
        .select(pl.col("provider"), pl.col("denominator"), pl.col("std_rate"))
        .collect()
        .to_dicts()
    )


@bp.route(route="v1/tpmas/rates/provider/provider={provider}/{tpma}", methods=["GET"])
@openapi(
    summary="Get TPMA rates for a provider",
    description="Returns rates for the specified provider and TPMA.",
    tags=["TPMA Rates"],
    path=ProviderPath,
    querystring=VersionQuery,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "schema": RatesByProvider,
                }
            },
        },
        400: {"description": "Invalid request parameters"},
    },
)
@handle_route_errors
def route_tpma_rates_for_provider(req: func.HttpRequest) -> func.HttpResponse:
    version = VersionQuery.model_validate(
        {"version": req.params.get("version", CURRENT_APP_VERSION)}
    ).version

    provider = ProviderPath.model_validate(
        {"provider": req.route_params.get("provider")}, context=version
    ).provider

    tpma = TPMAPath.model_validate({"tpma": req.route_params.get("tpma")}).tpma

    logger.info(
        "Request for rates by provider: version=%s, provider=%s, tpma=%s",
        version,
        provider,
        tpma,
    )

    rates = get_tpma_rates_for_provider(version, provider, tpma)
    return func.HttpResponse(json.dumps(rates), mimetype="application/json")


@bp.route(route="v1/tpmas/rates/provider/fyear={fyear}/{tpma}", methods=["GET"])
@openapi(
    summary="Get TPMA rates for a financial year",
    description="Returns rates for the specified financial year and TPMA.",
    tags=["TPMA Rates"],
    path=FinancialYearPath,
    querystring=VersionQuery,
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "schema": RatesByFyear,
                }
            },
        },
        400: {"description": "Invalid request parameters"},
    },
)
@handle_route_errors
def route_tpma_rates_for_fyear(req: func.HttpRequest) -> func.HttpResponse:
    version = VersionQuery.model_validate(
        {"version": req.params.get("version", CURRENT_APP_VERSION)}
    ).version
    fyear = FinancialYearPath.model_validate(
        {"fyear": req.route_params.get("fyear")}
    ).fyear
    tpma = TPMAPath.model_validate({"tpma": req.route_params.get("tpma")}).tpma

    fyear_int = int(fyear)

    logger.info(
        "Request for rates by fyear: version=%s, fyear=%s, tpma=%s",
        version,
        fyear_int,
        tpma,
    )

    rates = get_tpma_rates_for_fyear(version, fyear_int, tpma)
    return func.HttpResponse(json.dumps(rates), mimetype="application/json")
