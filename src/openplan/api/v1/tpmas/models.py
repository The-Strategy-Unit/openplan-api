from pydantic import BaseModel, TypeAdapter


class RateByProvider(BaseModel):
    fyear: int
    denominator: float
    std_rate: float


RatesByProvider = TypeAdapter(list[RateByProvider]).json_schema()


class RateByFyear(BaseModel):
    provider: str
    denominator: float
    std_rate: float


RatesByFyear = TypeAdapter(list[RateByFyear]).json_schema()
