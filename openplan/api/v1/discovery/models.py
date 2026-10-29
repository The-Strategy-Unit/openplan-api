from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator

from openplan.api.v1.models import FinancialYear, VersionQuery
from openplan.api.v1.reference.providers import ProviderIdentifier
from openplan.api.v1.tpmas import TPMAIdentifier

CalendarYear = Annotated[int, Field(ge=1900, le=9999)]
Variant = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[^/\\]+$")]


class PublishedModel(BaseModel):
    model_config = {"extra": "forbid"}


class DatasetRelease(VersionQuery):
    model_config = {"extra": "forbid"}
    version: str = Field(..., description="Dataset release identifier, e.g. dev or v1.0.")
    published_at: AwareDatetime
    source: str = Field(..., min_length=1, description="Publisher-supplied dataset source or provenance.")


class VersionsResponse(PublishedModel):
    versions: list[DatasetRelease]

    @field_validator("versions")
    @classmethod
    def unique_versions(cls, value: list[DatasetRelease]) -> list[DatasetRelease]:
        if len({release.version for release in value}) != len(value):
            raise ValueError("Dataset versions must be unique")
        return value


class DatasetIndex(VersionsResponse):
    schema_version: Literal[1]


class RateSelection(PublishedModel):
    fyear: FinancialYear
    providers: list[ProviderIdentifier] = Field(..., min_length=1)

    @field_validator("providers")
    @classmethod
    def unique_providers(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Providers must be unique within a financial year")
        return value


class RateDataset(PublishedModel):
    selections: list[RateSelection]
    units: dict[str, str] = Field(default_factory=dict, description="Publisher-defined units keyed by measure.")

    @model_validator(mode="after")
    def unique_years(self) -> Self:
        if len({selection.fyear for selection in self.selections}) != len(self.selections):
            raise ValueError("Rate financial years must be unique")
        return self


class DemographicSelection(PublishedModel):
    start_year: CalendarYear
    variant: Variant
    end_years: list[CalendarYear] = Field(..., min_length=1)

    @field_validator("end_years")
    @classmethod
    def validate_end_years(cls, value: list[int], info) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("Horizon years must be unique")
        start_year = info.data.get("start_year")
        if start_year is not None and any(year < start_year for year in value):
            raise ValueError("Horizon years must not precede the start year")
        return value


class DemographicDataset(PublishedModel):
    selections: list[DemographicSelection]
    units: dict[str, str] = Field(default_factory=dict, description="Publisher-defined units keyed by measure.")

    @model_validator(mode="after")
    def unique_selections(self) -> Self:
        keys = {(selection.start_year, selection.variant) for selection in self.selections}
        if len(keys) != len(self.selections):
            raise ValueError("Demographic start-year and variant pairs must be unique")
        return self


class DatasetManifest(DatasetRelease):
    schema_version: Literal[1]
    rates: dict[TPMAIdentifier, RateDataset]
    demographics: dict[ProviderIdentifier, DemographicDataset]


class RateAvailabilityResponse(DatasetRelease, RateDataset):
    tpma: TPMAIdentifier


class DemographicAvailabilityResponse(DatasetRelease, DemographicDataset):
    provider: ProviderIdentifier
