from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Optional, List

from ._base import BaseDataClass


class MatchStatus(IntEnum):
    PENDING = 1
    ONGOING = 2
    COMPLETED = 3


@dataclass
class Match(BaseDataClass):
    name: str
    created_by: str
    created_at: str = field(default=datetime.now().strftime("%m/%d/%Y %H:%M:%S"))
    password: Optional[str] = field(default=None)
    status: MatchStatus = field(default=MatchStatus.PENDING)
    teams_joined: List[str] = field(default_factory=list)
    teams_ready: List[str] = field(default_factory=list)

    def __str__(self):
        return (
            "```ldif\n"
            f"Status: {self.status.name}\n"
            f"Teams Joined: {len(self.teams_joined)}\n"
            f"Teams Ready: {len(self.teams_ready)}\n"
            f"Created by: {self.created_by}\n"
            f"Created at: {self.created_at}\n"
            "```"
        )
