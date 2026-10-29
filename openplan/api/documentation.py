import json
from typing import Any

import azure.functions as func
from azure_functions_openapi import get_openapi_json

ENTRA_SCHEME = {
    "type": "http",
    "scheme": "bearer",
    "bearerFormat": "JWT",
    "description": (
        "Microsoft Entra access token for this API's configured audience. "
        "Azure Easy Auth enforces authentication before application handlers run."
    ),
}

PLATFORM_AUTH_RESPONSES = {
    "302": {
        "description": "The deployed authentication platform redirects unauthenticated requests to Entra sign-in.",
        "headers": {
            "Location": {
                "description": "Authentication redirect URL",
                "schema": {"type": "string", "format": "uri-reference"},
            },
        },
    },
    "401": {"description": "The authentication platform rejected the supplied credentials."},
}


def build_openapi_document(app: func.FunctionApp) -> dict[str, Any]:
    document = json.loads(get_openapi_json(
        title="OpenPlan API", openapi_version="3.2.0", app=app, route_prefix="",
        security_schemes={"EntraBearer": ENTRA_SCHEME},
    ))
    document["security"] = [{"EntraBearer": []}]
    for path_item in document["paths"].values():
        for method in ("get", "put", "post", "delete", "options", "head", "patch", "trace"):
            if method in path_item:
                for status, response in PLATFORM_AUTH_RESPONSES.items():
                    path_item[method]["responses"].setdefault(status, response)
    return document
