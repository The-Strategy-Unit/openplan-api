from fastapi import Depends, FastAPI

from openplan.api import health
from openplan.api.documentation import BEARER_AUTH, PLATFORM_AUTH_RESPONSES, build_openapi_document
from openplan.api.v1 import demographics, discovery, tpmas
from openplan.api.v1.error_handling import register_error_handlers
from openplan.api.v1.reference import peers, providers
from openplan.api.v1.tpmas import rates


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpenPlan API", version="1.0.0",
        redoc_url=None, swagger_ui_oauth2_redirect_url=None,
        dependencies=[Depends(BEARER_AUTH)], responses=PLATFORM_AUTH_RESPONSES,
    )
    register_error_handlers(app)
    for router in (
        health.router, discovery.router, peers.router, providers.router,
        rates.router, demographics.router, tpmas.router,
    ):
        app.include_router(router)
    app.openapi = lambda: build_openapi_document(app)
    return app


app = create_app()
