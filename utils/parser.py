import itertools
from typing import Optional, List


def get_tournament_participant_by(tournament: dict, key, value) -> Optional[dict]:
    return next((p for p in tournament["info"]["teams"] if p[key] == value), None)


def get_tournament_registration_by(tournament: dict, key, value) -> Optional[dict]:
    return next((r for r in tournament["registrations"] if r[key] == value), None)


def get_tournament_match_by(tournament: dict, key, value) -> Optional[dict]:
    return next((m for m in tournament["matches"] if m[key] == value), None)


def get_tournament_administrator_by(tournament: dict, key, value) -> Optional[dict]:
    return next((a for a in tournament["administrators"] if a[key] == value), None)


def get_tournament_administrator_members(tournament: dict) -> List[str]:
    return list(
        itertools.chain(*list(a["members"] for a in tournament["administrators"]))
    )
