from plugins.tournament_manager.clients.toornament_api_client import ToornamentAPIClient
from plugins.tournament_manager.models import Tournament, ToornamentInfo, Team, Player
from plugins.tournament_manager.services.errors import (
    TournamentIDNotFound,
    TournamentTeamIDNotFound,
    ErrorFetchingParticipantData,
)


class TournamentService:
    def __init__(self, toornament_client: ToornamentAPIClient):
        self.toornament_client = toornament_client

    def create_tournament(self, tournament_id: int, alias: str) -> Tournament:
        # Get Toornament info
        toornament_info = self.toornament_client.get_tournament(tournament_id)
        if not toornament_info:
            raise TournamentIDNotFound(tournament_id)

        tournament = Tournament(
            id=tournament_id,
            alias=alias,
            url=f"https://www.toornament.com/en_US/tournaments/"
            f"{tournament_id}/information",
            info=ToornamentInfo.from_dict(toornament_info),
        )

        # Get Toornament participants
        toornament_participants = self.toornament_client.get_participants(tournament_id)
        tournament.teams = [Team.from_dict(p) for p in toornament_participants]

        return tournament

    def refresh_tournament(self, tournament: Tournament) -> Tournament:
        # update data fetched on Toornament
        info = self.toornament_client.get_tournament(tournament.id)
        if not info:
            raise TournamentIDNotFound(tournament.id)

        # Override current tournament info
        tournament.info = ToornamentInfo.from_dict(info)

        # update participants list
        participants = self.toornament_client.get_participants(tournament.id)
        for participant in participants:
            team = tournament.find_team_by_id(participant["id"])
            if team:
                # Update participant name and lineup
                team.name = participant["name"]
                team.lineup = [Player(**pl) for pl in participant.get("lineup", [])]
                team.checked_in = participant.get("checked_in")
            else:
                # Add new participant
                tournament.teams.append(Team.from_dict(participant))

        return tournament

    def reset_tournament_team(self, tournament: Tournament, team_id: int) -> Team:
        team = tournament.find_team_by_id(team_id)
        if not team:
            raise TournamentTeamIDNotFound(team_id, tournament.alias)

        participant = self.toornament_client.get_participant(tournament.id, int(team.id))
        if not participant:
            raise ErrorFetchingParticipantData(team_id, tournament.alias)

        team.captain = None
        team.lineup = [Player.from_dict(pl) for pl in participant["lineup"]]
        team.custom_fields = participant["custom_fields"]
        team.checked_in = participant.get("checked_in")

        return team

    @staticmethod
    def remove_tournament_team(tournament: Tournament, team_id: int) -> Team:
        team = tournament.find_team_by_id(team_id)
        if not team:
            raise TournamentTeamIDNotFound(team_id, tournament.alias)

        tournament.teams.remove(team)
        return team
