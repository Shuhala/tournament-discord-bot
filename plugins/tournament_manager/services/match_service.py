from typing import Optional

from plugins.tournament_manager.clients.toornament_api_client import ToornamentAPIClient
from plugins.tournament_manager.models import Match, MatchStatus
from plugins.tournament_manager.services.errors import InvalidMatchStatus, MatchIDNotFound


class MatchService:
    def __init__(self, toornament_client: ToornamentAPIClient):
        self.toornament_client = toornament_client

    def create_match(
        self,
        tournament_id: int,
        match_id: int,
        match_name: str,
        created_by: str,
        password: Optional[str] = None,
    ) -> Match:
        match = Match(
            id=match_id, name=match_name, created_by=created_by, password=password,
        )

        if match_id:
            match_info = self.toornament_client.get_match(tournament_id, match_id)
            if not match_info:
                raise MatchIDNotFound(match_id)

            match.group_name = match_info["public_notes"]
            match.teams_registered = [
                p["participant"]["id"] for p in match_info["opponents"]
            ]

        return match

    @staticmethod
    def set_match_status(match: Match, status: str) -> Match:
        if not hasattr(MatchStatus, status.upper()):
            raise InvalidMatchStatus(status)

        match.status = MatchStatus[status.upper()]
        return match
