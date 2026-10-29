from pydantic import BaseModel


class DemographicFactors(BaseModel):
    baseline: dict[str, dict[str, float | None]]
    horizon: dict[str, dict[str, float | None]]


class DemographicFactorsResponse(BaseModel):
    population: DemographicFactors
    births: DemographicFactors
