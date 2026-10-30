from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get(
    "/health", response_model=HealthResponse,
    summary="Check application liveness",
    description="Reports that the application is running. Does not check dataset availability or storage access.",
)
def route_health(response: Response) -> HealthResponse:
    response.headers["Cache-Control"] = "no-store"
    return HealthResponse(status="ok")
