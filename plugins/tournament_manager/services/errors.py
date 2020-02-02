from plugins.tournament_manager.models.match import MatchStatus


class AppError(Exception):
    def __init__(self, *args):
        super().__init__(
            f"{self.__class__.__name__}: " f"{', '.join(str(a) for a in args)}"
        )


class CantEndMatchWithStatus(AppError):
    pass


class ErrorFetchingParticipantData(AppError):
    def __init__(self, team_id: int, tournament_alias: str):
        message = (
            f"Could not fetch team id {team_id} data for "
            f"the tournament {tournament_alias}"
        )
        super().__init__(message)


class InvalidMatchStatus(AppError):
    def __init__(self, status: str):
        message = (
            f"Match status `{status}` doesn't exists. "
            f"Choices are: {[s.name for s in MatchStatus]}"
        )
        super().__init__(message)


class MatchIDNotFound(AppError):
    pass


class TournamentChannelNotFound(AppError):
    pass


class TournamentChannelExists(AppError):
    def __init__(self, channel, alias):
        message = f"Channel {channel} already exists for tournament {alias}"
        super().__init__(message)


class TournamentIDNotFound(AppError):
    pass


class TournamentRoleNotFound(AppError):
    pass


class TournamentMatchNameNotFound(AppError):
    pass


class TournamentNotFound(AppError):
    pass


class TournamentTeamIDNotFound(AppError):
    def __init__(self, team_id: int, tournament_alias: str):
        message = f"Team {team_id} not found in the tournament {tournament_alias}"
        super().__init__(message)
