from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from ._base import BaseDataClass


@dataclass
class ScoreSubmission(BaseDataClass):
    match_name: str
    team_name: str
    screenshot_links: List[str] = field(default_factory=list)
    position: Optional[int] = field(default=None)
    eliminations: Optional[int] = field(default=None)
    last_updated: str = field(default=datetime.now().strftime("%m/%d/%Y %H:%M:%S"))

    def get_screenshots(self) -> str:
        return ", ".join(f"<{u}>" for u in self.screenshot_links)

    def show_card(self) -> dict:
        return {
            "title": self.team_name,
            "fields": (
                ("Match", self.match_name),
                ("Position", self.position),
                ("Eliminations", self.eliminations),
                ("Last update", self.last_updated),
                ("Screenshots", self.get_screenshots()),
            ),
            "color": "grey",
        }

    def __str__(self):
        return (
            f"```Position:      {self.position}\n"
            f"Eliminations:  {self.eliminations}\n"
            f"Last update:   {self.last_updated}```" + "\n".join(self.screenshot_links)
        )
