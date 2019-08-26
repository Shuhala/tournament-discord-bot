from dataclasses import dataclass, field
from typing import Optional, List

from ._base import BaseDataClass


@dataclass
class ToornamentInfo(BaseDataClass):
    id: int
    country: str
    discipline: str
    location: str
    name: str
    scheduled_date_end: str
    scheduled_date_start: str
    size: int
    status: str
    team_max_size: int
    team_min_size: int
    rule: Optional[str] = field(default=None)
    prize: Optional[str] = field(default=None)
    platforms: List[str] = field(default_factory=list)
