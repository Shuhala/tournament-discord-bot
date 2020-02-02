from typing import Optional

from plugins.tournament_manager.clients.toornament_api_client import ToornamentAPIClient
from plugins.tournament_manager.models import (
    Match,
    Player,
    Team,
    ToornamentInfo,
    Tournament,
)
from plugins.tournament_manager.services.errors import (
    ErrorFetchingParticipantData,
    TournamentChannelExists,
    TournamentChannelNotFound,
    TournamentIDNotFound,
    TournamentMatchNameNotFound,
    TournamentRoleNotFound,
    TournamentTeamIDNotFound,
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
    def remove_admin_role(tournament: Tournament, role: str) -> Tournament:
        if role not in tournament.administrator_roles:
            raise TournamentRoleNotFound(role)
        tournament.administrator_roles.remove(role)
        return tournament

    @staticmethod
    def remove_captain_role(tournament: Tournament) -> Tournament:
        tournament.captain_role = None
        return tournament

    def remove_match(self, tournament: Tournament, match_name: str) -> Tournament:
        match = self.get_match_by_name(tournament, match_name)
        tournament.matches.remove(match)
        return tournament

    @staticmethod
    def remove_channel(tournament, channel) -> Tournament:
        if channel not in tournament.channels:
            raise TournamentChannelNotFound(channel)
        tournament.channels.remove(channel)
        return tournament

    @staticmethod
    def add_channel(tournament: Tournament, channel: str) -> Tournament:
        if channel in tournament.channels:
            raise TournamentChannelExists(channel, tournament)
        tournament.channels.append(channel)
        return tournament

    @staticmethod
    def find_match_by_name(tournament: Tournament, match_name: str) -> Optional[Match]:
        for match in tournament.matches:
            if match.name == match_name:
                return match
        return None

    def get_match_by_name(self, tournament: Tournament, match_name: str) -> Match:
        match = self.find_match_by_name(tournament, match_name)
        if not match:
            raise TournamentMatchNameNotFound(match_name)

        return match

    @staticmethod
    def set_captain_role(tournament: Tournament, role: str) -> Tournament:
        tournament.captain_role = role
        return tournament

    @staticmethod
    def remove_tournament_team(tournament: Tournament, team_id: int) -> Team:
        team = tournament.find_team_by_id(team_id)
        if not team:
            raise TournamentTeamIDNotFound(team_id, tournament.alias)

        tournament.teams.remove(team)
        return team
