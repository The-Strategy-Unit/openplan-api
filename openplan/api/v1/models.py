from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, ValidationInfo, field_validator

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
        raise ValueError("fyear must identify consecutive financial years, e.g. 202425")
    return value


FinancialYear = Annotated[
    str,
    Field(
        pattern=r"^[0-9]{6}$",
        description="Consecutive financial years in YYYYYY format, e.g. 202425 or 199900.",
    ),
    AfterValidator(validate_fyear),
]


def validation_version(info: ValidationInfo) -> str:
    """Use the model's validated version, or request context for path models."""
    return (info.data or {}).get(
        "version", (info.context or {}).get("version", CURRENT_APP_VERSION)
    )
