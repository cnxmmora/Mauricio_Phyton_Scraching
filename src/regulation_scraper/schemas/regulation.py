import uuid
from enum import StrEnum, auto
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, ConfigDict


class RegulationStatus(StrEnum):
    UNKNOWN = auto()
    ACTIVE = auto()
    REPEALED = auto()


class RegulationItem(BaseModel):
    id: UUID = Field(default_factory=uuid.uuid4)
    state: str
    link: HttpUrl
    external_reference_id: str
    name: str
    status: RegulationStatus = RegulationStatus.UNKNOWN

    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)


class RegulationUnit(RegulationItem):
    hierarchy: list[str]


class RegulationSection(RegulationItem):
    content: str
    unit_id: UUID
    index: int
    references: list[str] = Field(default_factory=list)
    media_links: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
