from datetime import datetime
from typing import Optional, List

from plugins.tournament_manager.clients.toornament_api_client import ToornamentAPIClient
from plugins.tournament_manager.models import (
    Match,
    Player,
    Team,
    ToornamentInfo,
    Tournament,
    MatchStatus,
    ScoreSubmission,
)
from plugins.tournament_manager.services.errors import (
    ErrorFetchingParticipantData,
    TournamentChannelExists,
    TournamentChannelNotFound,
    TournamentIDNotFound,
    TournamentMatchNameNotFound,
    TournamentRoleNotFound,
    TournamentTeamCaptainExists,
    TournamentTeamIDNotFound,
    TournamentTeamNameNotFound,
    GenericError,
    PermissionDeniedNotTeamCaptain,
)


class TournamentService:
    def __init__(self, toornament_client: ToornamentAPIClient):
        self.toornament_client = toornament_client

    @staticmethod
    def add_channel(tournament: Tournament, channel: str) -> Tournament:
        if channel in tournament.channels:
            raise TournamentChannelExists(channel, tournament)
        tournament.channels.append(channel)
        return tournament

    def add_screenshot(
        self, tournament: Tournament, match_name: str, team_id: int, urls: List[str]
    ) -> ScoreSubmission:
        match = self.get_match_by_name(tournament, match_name)
        team = self.get_team_by_id(tournament, int(team_id))

        # match completed, submissions locked
        if match.status == MatchStatus.COMPLETED:
            raise GenericError(
                f"Can't submit score for the match `{match.name}`. "
                f"Match status is set to COMPLETED. "
                f"Submissions are now locked. "
                f"Please contact your Tournament Administrator.",
            )
        score = team.find_submission_by_match(match.name)
        if not score:
            raise GenericError(
                f"No score submission found for the match `{match.name}`. "
                "Use `!submit [match_name] position [number] "
                "eliminations [number]` to submit your score.\n",
            )
        score.screenshot_links.extend(urls)
        score.updated_at = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

        return score

    def submit_score(
        self,
        tournament: Tournament,
        match_name: str,
        team_id: int,
        urls: List[str],
        position: int,
        eliminations: int,
    ) -> ScoreSubmission:
        match = self.get_match_by_name(tournament, match_name)
        team = self.get_team_by_id(tournament, int(team_id))

        # Team not registered in this game
        if match.id and team.id not in match.teams_registered:
            raise GenericError(
                "You are not authorized to submit a score for this match, "
                f"your team is not registered in this match group "
                f"`{match.group_name}`",
            )
        # match completed, submissions locked
        if match.status == MatchStatus.COMPLETED:
            raise GenericError(
                f"Can't submit score for the match `{match.name}`. "
                f"Match status is set to COMPLETED. "
                f"Submissions are now locked. "
                f"Please contact your Tournament Administrator.",
            )
        # score already submitted
        score = team.find_submission_by_match(match.name)
        if score:
            raise GenericError(
                f"Score for the match `{match.name}` already submitted.\n"
                f"Use `!remove score [match_name]` if you want to submit "
                f"a different score, or `!add screenshot [match_name]` to "
                f"add a screenshot to your submission.",
            )

        # add score
        score = ScoreSubmission(
            match_name=match.name,
            team_name=team.name,
            screenshot_links=urls,
            position=position,
            eliminations=eliminations,
        )
        team.score_submissions.append(score)

        return score

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

    @staticmethod
    def find_match_by_name(tournament: Tournament, match_name: str) -> Optional[Match]:
        for match in tournament.matches:
            if match.name == match_name:
                return match
        return None

    @staticmethod
    def find_team_by_name(tournament: Tournament, team_name: str) -> Optional[Team]:
        for t in tournament.teams:
            if t.name == team_name:
                return t
        return None

    @staticmethod
    def find_team_by_id(tournament: Tournament, team_id: int) -> Optional[Team]:
        for p in tournament.teams:
            if p.id == str(team_id):
                return p
        return None

    def find_captain_tournament_alias(
        self, tournaments: dict, captain_name: str
    ) -> Optional[str]:
        """
        Return the alias of the tournament for which the captain_name is linked to a team
        """
        for t in tournaments.values():
            tournament = Tournament.from_dict(t)
            team = self.find_captain_team(tournament, captain_name)
            if team:
                return tournament.alias

    def get_captain_tournament_alias(self, tournaments: dict, captain_name: str) -> str:
        alias = self.find_captain_tournament_alias(tournaments, captain_name)
        if not alias:
            raise PermissionDeniedNotTeamCaptain()
        return alias

    def find_captain_team(
        self, tournament: Tournament, captain_name: str
    ) -> Optional[Team]:
        for team in tournament.teams:
            if team.captain == captain_name:
                return team
        return None

    def get_captain_team(self, tournament: Tournament, captain_name: str) -> Team:
        team = self.find_captain_team(tournament, captain_name)
        if not team:
            raise PermissionDeniedNotTeamCaptain()
        return team

    def get_match_by_name(self, tournament: Tournament, match_name: str) -> Match:
        match = self.find_match_by_name(tournament, match_name)
        if not match:
            raise TournamentMatchNameNotFound(match_name)

        return match

    def get_team_by_id(self, tournament: Tournament, team_id: int) -> Team:
        team = self.find_team_by_id(tournament, team_id)
        if not team:
            raise TournamentTeamIDNotFound(team_id)
        return team

    def get_team_by_name(self, tournament: Tournament, team_name: str) -> Team:
        team = self.find_team_by_name(tournament, team_name)
        if not team:
            raise TournamentTeamNameNotFound(team_name)
        return team

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
            team = self.find_team_by_id(tournament, participant["id"])
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
        team = self.get_team_by_id(tournament, team_id)

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

    def link_team_captain(
        self, tournament: Tournament, team_name: str, captain_name: str
    ) -> Team:
        team = self.get_team_by_name(tournament, team_name)
        if team.captain is not None:
            raise TournamentTeamCaptainExists(team_name, team.captain)

        team.captain = captain_name
        return team

    @staticmethod
    def set_captain_role(tournament: Tournament, role: str) -> Tournament:
        tournament.captain_role = role
        return tournament

    def remove_tournament_team(self, tournament: Tournament, team_id: int) -> Team:
        team = self.get_team_by_id(tournament, team_id)
        tournament.teams.remove(team)
        return team
