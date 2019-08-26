from dataclasses import dataclass, field
from typing import Optional, List

from ._base import BaseDataClass
from .match import Match
from .score_submission import ScoreSubmission
from .team import Team
from .toornament_info import ToornamentInfo


@dataclass
class Tournament(BaseDataClass):
    id: int
    alias: str
    info: ToornamentInfo = field(default=None)
    administrator_roles: List[str] = field(default_factory=list)
    captain_role: str = field(default=None)
    channels: List[str] = field(default_factory=list)
    matches: List[Match] = field(default_factory=list)
    teams: List[Team] = field(default_factory=list)
    url: Optional[str] = field(default=None)

    def count_linked_teams(self) -> int:
        return sum([p.captain is not None for p in self.teams])

    def find_match_by_name(self, name: str) -> Optional[Match]:
        for m in self.matches:
            if m.name == name:
                return m
        return None

    def find_team_by_captain(self, captain_name: str) -> Optional[Team]:
        for p in self.teams:
            if p.captain == captain_name:
                return p
        return None

    def find_team_by_id(self, team_id: int) -> Optional[Team]:
        for p in self.teams:
            if p.id == str(team_id):
                return p
        return None

    def find_team_by_name(self, team_name: str) -> Optional[Team]:
        for p in self.teams:
            if p.name == team_name:
                return p
        return None

    def get_match_scores(self, match_name: str) -> List[ScoreSubmission]:
        submissions = []
        for team in self.teams:
            submission = team.find_submission_by_match(match_name)
            if submission:
                submissions.append(submission)

        return submissions

    def show_card(self) -> dict:
        return {
            "title": f"{self.alias} ({self.info.name})",
            "link": self.url,
            "fields": (
                ("Tournament Alias", str(self.alias)),
                ("Toornament ID", str(self.info.id)),
                ("Game", self.info.discipline),
                ("Linked Teams", str(self.count_linked_teams())),
                ("Registered Teams", str(len(self.teams))),
                ("Bot Channels", "\n".join(self.channels) or None),
                ("Captain Role", f"@{self.captain_role}" if self.captain_role else None),
                (
                    "Tournament Administrator Roles",
                    ", ".join(f"@{r}" for r in self.administrator_roles) or None,
                ),
            ),
        }
