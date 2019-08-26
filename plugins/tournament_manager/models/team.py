from dataclasses import dataclass, field
from typing import Optional, List

from ._base import BaseDataClass
from .player import Player
from .score_submission import ScoreSubmission


@dataclass
class Team(BaseDataClass):
    id: int
    name: str
    custom_fields: List[str] = field(default_factory=list)
    lineup: List[Player] = field(default_factory=list)
    captain: Optional[str] = field(default=None)
    checked_in: Optional[bool] = field(default=None)
    score_submissions: List[ScoreSubmission] = field(default_factory=list)

    def find_submission_by_match(self, match_name: str) -> Optional[ScoreSubmission]:
        for s in self.score_submissions:
            if s.match_name == match_name:
                return s
        return None

    def show_card(self) -> dict:
        return {
            "fields": (
                ("Team Name", self.name),
                ("Team ID", self.id),
                ("Team Captain", self.captain),
                ("Team Players", "\n".join(pl.name for pl in self.lineup)),
            ),
            "color": "grey",
        }
