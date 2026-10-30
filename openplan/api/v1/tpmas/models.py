from typing import Self

from pydantic import BaseModel, model_validator

from openplan.api.v1.models import FinancialYear, VersionQuery
from openplan.api.v1.reference.providers import ProviderIdentifier


class RatesQuery(VersionQuery):
    provider: ProviderIdentifier | None = None
    fyear: FinancialYear | None = None

    @model_validator(mode="after")
    def require_filter(self) -> Self:
        if self.provider is None and self.fyear is None:
            raise ValueError("At least one of provider or fyear must be supplied")
        return self


class Rate(BaseModel):
    model_config = {"allow_inf_nan": False}
    provider: str
    fyear: int
    denominator: float
    std_rate: float
