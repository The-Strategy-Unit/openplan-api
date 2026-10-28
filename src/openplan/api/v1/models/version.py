from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from openplan.api.v1.settings import CURRENT_APP_VERSION


class VersionQuery(BaseModel):
    version: str = Field(
        default=CURRENT_APP_VERSION,
        description="API version, for example dev or v1.0.",
    )

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not cls.is_valid_version(value):
            raise ValueError("version must match dev or v<major>.<minor>[.<patch>]")
        return value

    @staticmethod
    def is_valid_version(version: str) -> bool:
        return bool(re.match(r"^(dev|v\d+\.\d+(\.\d+)?)$", version))
