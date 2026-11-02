"""Authorize principals supplied by the enforced Azure Easy Auth boundary."""

import base64
import binascii
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

DATA_READ_ROLE = "OpenPlan.Data.Read"


class _Claim(BaseModel):
    typ: str
    val: str


class _ClientPrincipal(BaseModel):
    claims: list[_Claim] = Field(default_factory=list)
    role_typ: str = "roles"


def get_client_principal(request: Request) -> _ClientPrincipal:
    value = request.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not value:
        raise ValueError("No authenticated client principal")
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
        return _ClientPrincipal.model_validate_json(decoded, strict=True)
    except (ValueError, TypeError, binascii.Error):
        raise ValueError("Invalid authenticated client principal") from None


def get_roles(request: Request) -> set[str]:
    principal = get_client_principal(request)
    # Easy Auth can map role claims to the type named by role_typ.
    role_types = {"roles", principal.role_typ}
    return {claim.val for claim in principal.claims if claim.typ in role_types}


def has_role(request: Request, *required_roles: str) -> bool:
    return bool(get_roles(request) & set(required_roles))


def require_role(*roles: str) -> Callable[[Request], Awaitable[None]]:
    if not roles:
        raise ValueError("At least one required role must be supplied")

    async def check_roles(request: Request) -> None:
        try:
            authorized = has_role(request, *roles)
        except (TypeError, ValueError):
            raise HTTPException(status_code=401, detail="Unauthorized") from None
        if not authorized:
            raise HTTPException(status_code=403, detail="Forbidden")

    return check_roles
