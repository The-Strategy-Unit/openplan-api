from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, field_validator

from openplan.api.v1.error_handling import is_valid_fyear, is_valid_version
from openplan.api.v1.settings import CURRENT_APP_VERSION


class VersionQuery(BaseModel):
    version: str = Field(
        default=CURRENT_APP_VERSION,
        description="Dataset version, for example dev or v1.0.",
    )

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not is_valid_version(value):
            raise ValueError("version must match dev or v<major>.<minor>[.<patch>]")
        return value


def validate_fyear(value: str) -> str:
    if not is_valid_fyear(value):
        raise ValueError("fyear must be a 6-digit financial year value")
    return value


FinancialYear = Annotated[
    str,
    Field(
        pattern=r"^\d{6}$",
        description="Financial year in YYYYYY format, e.g. 202425.",
    ),
    AfterValidator(validate_fyear),
]
