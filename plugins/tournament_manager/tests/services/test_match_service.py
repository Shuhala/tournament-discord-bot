from unittest import TestCase
from unittest.mock import Mock

from ...models import Match, MatchStatus
from ...services.errors import GenericError
from ...services.match_service import MatchService


class TestMatchService(TestCase):
    def test_join_match(self):
        match = Match(
            id=1,
            name="Match",
            status=MatchStatus.PENDING,
            created_by="testUser",
            teams_registered=["1", "2"],
            teams_joined=["1"],
        )
        self.assertEqual(2, len(match.teams_registered))
        self.assertEqual(1, len(match.teams_joined))

        match_service = MatchService(Mock())

        # team already joined
        self.assertRaises(GenericError, match_service.join_match, match, 1, "name")

        # match already started
        match.status = MatchStatus.ONGOING
        self.assertRaises(GenericError, match_service.join_match, match, 1, "name")

        # not authorized, team not in match group
        match.status = MatchStatus.PENDING
        self.assertRaises(GenericError, match_service.join_match, match, 4, "name")

        # joined
        match.status = MatchStatus.PENDING
        match_service.join_match(match, 2, "name")
        self.assertEqual(2, len(match.teams_joined))
