class AppError(Exception):
    def __init__(self, *args):
        super().__init__(f"{self.__class__.__name__}: ({', '.join(a for a in args)})")


class TournamentIDNotFound(AppError):
    pass


class TournamentTeamIDNotFound(AppError):
    def __init__(self, team_id: int, tournament_alias: str):
        message = f"Team {team_id} not found in the tournament {tournament_alias}"
        super().__init__(message)


class ErrorFetchingParticipantData(AppError):
    def __init__(self, team_id: int, tournament_alias: str):
        message = (
            f"Could not fetch team id {team_id} data for "
            f"the tournament {tournament_alias}"
        )
        super().__init__(message)
