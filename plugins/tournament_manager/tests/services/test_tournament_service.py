from unittest import TestCase
from unittest.mock import Mock

from plugins.tournament_manager.services.tournament_service import TournamentService
from ..utils import load_resource
from ...models import Tournament, Player
from ...services.errors import TournamentTeamIDNotFound, ErrorFetchingParticipantData


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
            "Should throw an error if Team ID doesn't exists",
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

    @staticmethod
    def _create_default_tournament(alias: str = "Test Tournament") -> Tournament:
        get_tournament = load_resource("get_tournament.json")
        get_participants = load_resource("get_participants.json")

        toornament_c_mock = Mock()
        toornament_c_mock.get_tournament.return_value = get_tournament
        toornament_c_mock.get_participants.return_value = get_participants
        tournament_service = TournamentService(toornament_c_mock)

        return tournament_service.create_tournament(get_tournament.get("id"), alias)
