from unittest import TestCase
from unittest.mock import Mock

from plugins.tournament_manager.services.tournament_service import TournamentService
from ..utils import load_resource
from ...models import Tournament, Player, Match
from ...services.errors import (
    TournamentTeamIDNotFound,
    ErrorFetchingParticipantData,
    TournamentRoleNotFound,
    TournamentMatchNameNotFound,
)


class TestTournamentService(TestCase):
    def test_create_tournament(self):
        # prepare
        get_tournament = load_resource("get_tournament.json")
        get_participants = load_resource("get_participants.json")
        self.assertEqual(4, len(get_participants))

        toornament_c_mock = Mock()
        toornament_c_mock.get_tournament.return_value = get_tournament
        toornament_c_mock.get_participants.return_value = get_participants
        tournament_service = TournamentService(toornament_c_mock)

        alias = "Test Tournament"

        # execute
        tournament = tournament_service.create_tournament(get_tournament.get("id"), alias)

        # assert
        self.assertEqual(alias, tournament.alias)
        self.assertEqual(get_tournament.get("id"), tournament.id)
        self.assertEqual(4, len(tournament.teams))

    def test_remove_tournament_team(self):
        # prepare
        tournament = self._create_default_tournament()
        self.assertEqual(4, len(tournament.teams), "Tournament should have 4 teams")

        tournament_service = TournamentService(Mock())

        # execute
        team = tournament_service.remove_tournament_team(tournament, 3)

        # assert
        self.assertEqual(3, int(team.id), "Should find the right ID")
        self.assertEqual(3, len(tournament.teams), "Tournament should now have 3 teams")

        self.assertRaises(
            TournamentTeamIDNotFound,
            tournament_service.remove_tournament_team,
            tournament,
            99,
        )

    def test_reset_tournament_team(self):
        tournament = self._create_default_tournament()
        team = tournament.teams[0]
        team.captain = "Captain"
        team.lineup = [Player(name="P1")]

        toornament_c_mock = Mock()
        tournament_service = TournamentService(toornament_c_mock)

        self.assertRaises(
            TournamentTeamIDNotFound,
            tournament_service.reset_tournament_team,
            tournament,
            99,
        )

        toornament_c_mock.get_participant.return_value = None

        self.assertRaises(
            ErrorFetchingParticipantData,
            tournament_service.reset_tournament_team,
            tournament,
            int(team.id),
        )

        get_participant = load_resource("get_participant.json")
        toornament_c_mock.get_participant.return_value = get_participant

        self.assertIsNotNone(team.captain)
        self.assertEqual(1, len(team.lineup))

        tournament_service.reset_tournament_team(tournament, int(team.id))

        self.assertIsNone(team.captain)
        self.assertEqual(2, len(team.lineup))

    def test_remove_admin_role(self):
        tournament_service = TournamentService(Mock())
        tournament = Tournament(alias="Test", id=123, administrator_roles=["a", "b"])

        self.assertEqual(2, len(tournament.administrator_roles))

        self.assertRaises(
            TournamentRoleNotFound, tournament_service.remove_admin_role, tournament, "c"
        )
        tournament_service.remove_admin_role(tournament, "b")
        self.assertEqual(1, len(tournament.administrator_roles))

    def test_remove_channel(self):
        tournament = Tournament(alias="Test", id=123, channels=["a", "b"])
        tournament_service = TournamentService(Mock())
        self.assertEqual(2, len(tournament.channels))

        self.assertRaises(
            TournamentRoleNotFound, tournament_service.remove_admin_role, tournament, "c"
        )

        tournament_service.remove_channel(tournament, "b")
        self.assertEqual(1, len(tournament.channels))

    def test_remove_match(self):
        match_name = "Match"
        tournament = Tournament(alias="Test", id=123)
        tournament.matches.append(Match(name=match_name, created_by="Test"))
        self.assertEqual(1, len(tournament.matches))

        tournament_service = TournamentService(Mock())

        self.assertRaises(
            TournamentMatchNameNotFound,
            tournament_service.remove_match,
            tournament,
            "Unknown",
        )
        tournament_service.remove_match(tournament, match_name)
        self.assertEqual(0, len(tournament.matches))

    @staticmethod
    def _create_default_tournament(alias: str = "Test Tournament") -> Tournament:
        get_tournament = load_resource("get_tournament.json")
        get_participants = load_resource("get_participants.json")

        toornament_c_mock = Mock()
        toornament_c_mock.get_tournament.return_value = get_tournament
        toornament_c_mock.get_participants.return_value = get_participants
        tournament_service = TournamentService(toornament_c_mock)

        return tournament_service.create_tournament(get_tournament.get("id"), alias)
