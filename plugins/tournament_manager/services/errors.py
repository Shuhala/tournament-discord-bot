from plugins.tournament_manager.models.match import MatchStatus


class AppError(Exception):
    def __init__(self, *args):
        super().__init__(
            f"{self.__class__.__name__}: " f"{', '.join(f'{a}' for a in args)}"
        )


class GenericError(AppError):
    def __init__(self, message="Something went wrong"):
        super().__init__(message)


class CantEndMatchWithStatus(AppError):
    pass


class ErrorFetchingParticipantData(AppError):
    def __init__(self, team_id: int, tournament_alias: str):
        super().__init__(
            f"Could not fetch team id {team_id} data for "
            f"the tournament {tournament_alias}"
        )


class InvalidMatchStatus(AppError):
    def __init__(self, status: str):
        super().__init__(
            f"Match status `{status}` doesn't exists. "
            f"Choices are: {[s.name for s in MatchStatus]}"
        )


class MatchIDNotFound(AppError):
    pass


class PermissionDeniedNotTeamCaptain(AppError):
    def __init__(self, *args):
        super().__init__("You are not a team captain")


class CantStartMatchWithStatus(AppError):
    pass


class TournamentChannelNotFound(AppError):
    pass


class TournamentChannelExists(AppError):
    def __init__(self, channel: str, alias: str):
        super().__init__(f"Channel {channel} already exists for tournament {alias}")


class TournamentIDNotFound(AppError):
    pass


class TournamentRoleNotFound(AppError):
    pass


class TournamentMatchNameNotFound(AppError):
    def __init__(self, match_name: str):
        super().__init__(f"There is no match with the name {match_name}")


class TournamentTeamIDNotFound(AppError):
    pass


class TournamentTeamNameNotFound(AppError):
    pass


class TournamentTeamCaptainExists(AppError):
    def __init__(self, team_name: str, captain_name: str):
        super().__init__(
            f"Team `{team_name}` already registered to the captain `{captain_name}`"
        )


class TournamentNotFound(AppError):
    pass
