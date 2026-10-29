import re

import azure.functions as func
from pydantic import BaseModel, Field, field_validator


class FinancialYearPath(BaseModel):
    fyear: str = Field(
        ...,
        pattern=r"^\d{6}$",
        description="Financial year in YYYYYY format, e.g. 202425.",
    )

    @field_validator("fyear")
    @classmethod
    def validate_fyear(cls, value: str) -> str:
        if not cls.is_valid_fyear(value):
            raise ValueError("fyear must be a 6-digit financial year value")
        return value

    @staticmethod
    def is_valid_fyear(fyear: str) -> bool:
        m = re.match(r"^(?:19|20)(\d{2})(\d{2})$", fyear)
        if not m:
            return False
        start_year, end_year = int(m.group(1)), int(m.group(2))

        return (start_year + 1) % 100 == end_year


def financial_year_path_validate(req: func.HttpRequest) -> str:
    return FinancialYearPath.model_validate(
        {"fyear": req.route_params.get("fyear")}
    ).fyear
