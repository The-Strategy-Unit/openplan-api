from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBearer

BEARER_AUTH = HTTPBearer(
    scheme_name="EntraBearer", bearerFormat="JWT", auto_error=False,
    description=(
        "Microsoft Entra access token for this API's configured audience. "
        "Azure Easy Auth enforces authentication before application handlers run. "
        "Local hosting does not reproduce that authentication boundary."
    ),
)

PLATFORM_AUTH_RESPONSES = {
    302: {
        "description": "The deployed authentication platform redirects unauthenticated requests to Entra sign-in.",
        "headers": {
            "Location": {
                "description": "Authentication redirect URL",
                "schema": {"type": "string", "format": "uri-reference"},
            },
        },
    },
    401: {"description": "The authentication platform rejected the supplied credentials."},
}


def build_openapi_document(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema is None:
        document = get_openapi(
            title=app.title, version=app.version, openapi_version=app.openapi_version,
            description=app.description, routes=app.routes,
        )
        document["security"] = [{"EntraBearer": []}]
        # Request validation uses our established 400 envelope instead of 422.
        for path_item in document["paths"].values():
            for method in ("get", "put", "post", "delete", "options", "head", "patch", "trace"):
                if method in path_item:
                    path_item[method]["responses"].pop("422", None)
        app.openapi_schema = document
    return app.openapi_schema
