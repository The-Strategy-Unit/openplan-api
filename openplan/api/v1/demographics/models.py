from pydantic import BaseModel


class DemographicFactors(BaseModel):
    model_config = {"coerce_numbers_to_str": True, "allow_inf_nan": False}
    baseline: dict[str, dict[str, float | None]]
    horizon: dict[str, dict[str, float | None]]


class DemographicFactorsResponse(BaseModel):
    population: DemographicFactors
    births: DemographicFactors
