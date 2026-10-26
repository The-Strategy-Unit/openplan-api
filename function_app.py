import logging

import azure.functions as func
from azure_functions_openapi import get_openapi_json, render_swagger_ui

from openplan.api.v1 import demographics, tpmas
from openplan.api.v1.reference import peers, providers
from openplan.api.v1.tpmas import rates

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
logger = logging.getLogger(__name__)


@app.route(route="openapi.json", methods=["GET"])
def openapi_json(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        get_openapi_json(
            title="OpenPlan API", openapi_version="3.2.0", app=app, route_prefix=""
        ),
        mimetype="application/json",
    )


@app.route(route="docs", methods=["GET"])
def swagger_ui(req: func.HttpRequest) -> func.HttpResponse:
    return render_swagger_ui(openapi_url="/openapi.json")


app.register_blueprint(peers.bp)
app.register_blueprint(providers.bp)
app.register_blueprint(rates.bp)
app.register_blueprint(demographics.bp)
app.register_blueprint(tpmas.bp)
