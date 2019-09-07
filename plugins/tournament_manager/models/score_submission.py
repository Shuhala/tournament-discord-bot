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
    updated_at: str = field(default=datetime.now().strftime("%m/%d/%Y %H:%M:%S"))

    def get_screenshots(self) -> str:
        return ", ".join(f"<{u}>" for u in self.screenshot_links)

    def show_card(self) -> dict:
        return {
            "title": self.team_name,
            "fields": (
                ("Match", self.match_name),
                ("Position", self.position),
                ("Eliminations", self.eliminations),
                ("Calculated Points", self.count_points()),
                ("Updated at", self.updated_at),
                ("Screenshots", self.get_screenshots()),
            ),
            "color": "grey",
        }

    def count_points(self) -> int:
        position_points = {
            1: 15,
            2: 12,
            3: 9,
            4: 9,
            5: 6,
            6: 6,
            7: 6,
            8: 6,
            9: 3,
            10: 3,
            11: 3,
            12: 3,
        }
        return position_points.get(self.position, 0) + self.eliminations

    def __str__(self):
        return (
            f"```ldif\nPosition:           {self.position}\n"
            f"Eliminations:       {self.eliminations}\n"
            f"Updated at:         {self.updated_at}\n"
            f"Calculated points:  {self.count_points()}```"
            + "\n".join(self.screenshot_links)
        )
