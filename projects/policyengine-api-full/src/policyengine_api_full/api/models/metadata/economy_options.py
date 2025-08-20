from pydantic import BaseModel


class Region(BaseModel):
    name: str
    label: str


class TimePeriod(BaseModel):
    name: int
    label: str


class EconomyOptions(BaseModel):
    region: list[Region]
    time_period: list[TimePeriod]
