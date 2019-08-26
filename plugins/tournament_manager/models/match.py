from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, List

from ._base import BaseDataClass
from .team import Team


class MatchStatus(IntEnum):
    PENDING = 1
    ONGOING = 2
    COMPLETED = 3


@dataclass
class Match(BaseDataClass):
    name: str
    created_by: str
    password: Optional[str] = field(default=None)
    status: MatchStatus = field(default=MatchStatus.PENDING)
    teams_ready: List[Team] = field(default_factory=list)

    def find_team_by_name(self, team_name: str) -> Optional[Team]:
        for team in self.teams_ready:
            if team.name == team_name:
                return team
        return None

    def __str__(self):
        return (
            f"**Status:** {self.status.name}\n"
            f"**Teams Ready:** {len(self.teams_ready)}\n"
            f"**Created by:** {self.created_by}\n"
        )
