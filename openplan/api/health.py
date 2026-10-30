from typing import Literal

import azure.functions as func
from azure_functions_openapi import openapi
from pydantic import BaseModel

bp = func.Blueprint()


class HealthResponse(BaseModel):
    status: Literal["ok"]


@bp.route("health", methods=["GET"])
@openapi(
    summary="Check application liveness",
    description="Reports that the application is running. Does not check dataset availability or storage access.",
    tags=["Health"],
    responses={200: HealthResponse},
)
def route_health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        HealthResponse(status="ok").model_dump_json(),
        mimetype="application/json",
        headers={"Cache-Control": "no-store"},
    )
