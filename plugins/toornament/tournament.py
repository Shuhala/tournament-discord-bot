import logging
from dataclasses import dataclass, field, fields, asdict, is_dataclass
from enum import IntEnum

import discord
from errbot import BotPlugin, botcmd, Message, arg_botcmd

from backends.discord.discord import DiscordPerson
from clients.toornament_api_client import ToornamentAPIClient
from utils.parser import *

logger = logging.getLogger(__name__)


class MatchStatus(IntEnum):
    PENDING = 1
    ONGOING = 2
    COMPLETED = 3


@dataclass
class BaseDataClass:
    def __post_init__(self):
        """
        Convert all fields of type `dataclass` into an instance of the
        specified data class if the current value is of type dict.

        There's some real sketchy stuff here bro.
        """

        def unpack_values(field_type, val):
            """ unpack dict if field exists for this type """
            return field_type(
                **{
                    k: v
                    for k, v in val.items()
                    if k in {ft.name for ft in fields(field_type)}
                }
            )

        cls = type(self)
        for f in fields(cls):
            is_list_of_dataclass = (
                hasattr(f.type, "_name")
                and f.type._name == "List"
                and is_dataclass(next(iter(f.type.__args__), None))
            )
            # if the field is not a dataclass, OR is not a List of dataclasses
            if not is_dataclass(f.type) and not is_list_of_dataclass:
                continue

            value = getattr(self, f.name)

            if isinstance(value, dict):
                new_value = unpack_values(f.type, value)
                setattr(self, f.name, new_value)
            elif isinstance(value, list):
                new_value = []
                for v in value:
                    if isinstance(v, dict):
                        new_value.append(unpack_values(f.type.__args__[0], v))
                setattr(self, f.name, new_value)

    @classmethod
    def from_dict(cls, values: dict):
        class_fields = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in values.items() if k in class_fields})

    def to_dict(self):
        return asdict(self)


@dataclass
class Player(BaseDataClass):
    name: str
    custom_fields: List[str] = field(default_factory=list)


@dataclass
class Team(BaseDataClass):
    id: int
    name: str
    custom_fields: List[str] = field(default_factory=list)
    lineup: List[Player] = field(default_factory=list)
    captain: Optional[str] = field(default=None)


@dataclass
class Match(BaseDataClass):
    name: str
    created_by: str
    status: MatchStatus = field(default=MatchStatus.PENDING)
    teams_ready: List[Team] = field(default_factory=list)

    def find_team_by_name(self, team_name: str) -> Optional[Team]:
        for team in self.teams_ready:
            if team.name == team_name:
                return team
        return None


@dataclass
class ToornamentInfo(BaseDataClass):
    id: int
    country: str
    discipline: str
    location: str
    name: str
    scheduled_date_end: str
    scheduled_date_start: str
    size: int
    status: str
    team_max_size: int
    team_min_size: int
    rule: Optional[str] = field(default=None)
    prize: Optional[str] = field(default=None)
    platforms: List[str] = field(default_factory=list)


@dataclass
class Tournament(BaseDataClass):
    tournament_id: int
    info: ToornamentInfo = field(default=None)
    administrator_roles: List[str] = field(default_factory=list)
    channels: List[str] = field(default_factory=list)
    matches: List[Match] = field(default_factory=list)
    teams: List[Team] = field(default_factory=list)
    url: Optional[str] = field(default=None)

    def count_registered_participants(self) -> int:
        return sum([p.captain is not None for p in self.teams])

    def find_match_by_name(self, name: str) -> Optional[Match]:
        for m in self.matches:
            if m.name == name:
                return m
        return None

    def find_team_by_captain(self, captain_name: str) -> Optional[Team]:
        for p in self.teams:
            if p.captain == captain_name:
                return p
        return None

    def find_team_by_id(self, participant_id: int) -> Optional[Team]:
        for p in self.teams:
            if p.id == participant_id:
                return p
        return None

    def find_team_by_name(self, team_name: str) -> Optional[Team]:
        for p in self.teams:
            if p.name == team_name:
                return p
        return None


class TournamentBotPlugin(BotPlugin):
    """
    TODO: Optional tournament ID if wrote in right channel
    """

    toornament_api_client = None

    def activate(self):
        """ Triggers on plugin activation """
        super(TournamentBotPlugin, self).activate()
        self.toornament_api_client = ToornamentAPIClient()
        if "tournaments" not in self:
            self["tournaments"] = {}

    def callback_attachment(self, msg: Message, discord_msg: discord.Message):
        print("Received a Discord message with attachemnts")

    @arg_botcmd(
        "--channels",
        type=str,
        nargs="+",
        default=[],
        help="Default channels to use some bot features",
    )
    @arg_botcmd("--roles", type=str, nargs="+", default=[], help="Administrator roles")
    @arg_botcmd("tournament_id", type=int)
    def add_tournament(self, msg: Message, tournament_id: int, channels, roles):
        with self.mutable("tournaments") as tournaments:
            if tournament_id not in tournaments:
                tournament = Tournament(
                    tournament_id=tournament_id,
                    url=f"https://www.toornament.com/en_US/tournaments/"
                    f"{tournament_id}/information",
                )

                if channels:
                    for channel in channels:
                        try:
                            self.query_room(channel)
                        except Exception:
                            return "Invalid channel name"
                        else:
                            tournament.channels.append(channel)

                if roles:
                    for role in roles:
                        if self._bot.find_role(role):
                            tournament.administrator_roles.extend(roles)
                        else:
                            return "Invalid role name"

                # Toornament info
                toornament_info = self.toornament_api_client.get_tournament(tournament_id)
                if not toornament_info:
                    return "Tournament not found."
                tournament.info = ToornamentInfo.from_dict(toornament_info)

                # Toornament participants
                toornament_participants = self.toornament_api_client.get_participants(
                    tournament_id
                )
                tournament.teams = [Team.from_dict(p) for p in toornament_participants]

                # Add to tournaments db
                tournaments.update({tournament_id: tournament.to_dict()})
                return f"Tournament `{tournament.info.name}` successfully added"

            return "Tournament already added."

    @arg_botcmd(
        "--channels",
        type=str,
        nargs="+",
        default=[],
        help="Default channels to use some bot features",
    )
    @arg_botcmd("--roles", type=str, nargs="+", default=[], help="Administrator roles")
    @arg_botcmd("tournament_id", type=int)
    def update_tournament(self, msg: Message, tournament_id: int, channels, roles):
        if tournament_id not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])

            if channels:
                for channel in channels:
                    try:
                        self.query_room(channel)
                    except Exception:
                        return "Invalid channel name"
                    else:
                        tournament.channels.append(channel)

            if roles:
                for role in roles:
                    if self._bot.find_role(role):
                        tournament.administrator_roles.extend(roles)
                    else:
                        return "Invalid role name"

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})
            return f"Tournament {tournament.info.name} updated"

    @arg_botcmd("tournament_id", type=int)
    def refresh_tournament(self, msg: Message, tournament_id: int):
        """ Refresh a tournament's information """
        if tournament_id not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])

            # update data fetched on Toornament
            info = self.toornament_api_client.get_tournament(tournament_id)
            if not info:
                return "Tournament not found on Toornament."

            # Override current tournament info
            tournament.info = ToornamentInfo.from_dict(**info)

            # update participants list
            participants = self.toornament_api_client.get_participants(tournament_id)
            for participant in participants:
                p = tournament.find_team_by_id(participant["id"])
                if p:
                    # Update participant name and lineup
                    p.name = participant["name"]
                    p.lineup = [Player(**pl) for pl in participant["lineup"]]
                else:
                    # Add new participant
                    tournament.teams.append(Team.from_dict(participant))

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})

    @arg_botcmd("tournament_id", type=int)
    def show_tournament(self, msg, tournament_id):
        if tournament_id not in self["tournaments"]:
            return "Tournament not found."
        tournament = Tournament.from_dict(self["tournaments"][tournament_id])
        self._send_tournament_info(msg, tournament)

    @botcmd
    def show_tournaments(self, msg, args):
        for tournament in self["tournaments"].values():
            tournament = Tournament.from_dict(tournament)
            self._send_tournament_info(msg, tournament)

    @arg_botcmd("discord_role", type=str)
    @arg_botcmd("tournament_id", type=int)
    def add_role(self, msg, tournament_id, discord_role):
        """ Associate a Discord role to a tournament """
        if tournament_id not in self["tournaments"]:
            return "Tournament not found."

        role = self._bot.find_role(discord_role)
        if not role:
            return f"Role `{discord_role}` not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])

            if role.name in tournament.administrator_roles:
                return (
                    f"`{role.name}` is already a tournament administrator role "
                    f"of `{tournament.info.name}`"
                )
            tournament.administrator_roles.append(role.name)

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})
            return f"Role `{role.name}` added to tournament `{tournament.info.name}`"

    @arg_botcmd("discord_role", type=str)
    @arg_botcmd("tournament_id", type=int)
    def remove_role(self, msg, tournament_id, discord_role):
        """ Remove an associated Discord role from a tournament """
        if tournament_id not in self["tournaments"]:
            return "Tournament not found."

        role = self._bot.find_role(discord_role)
        if not role:
            return f"Role `{discord_role}` not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])

            if role.name not in tournament.administrator_roles:
                return (
                    f"`{role.name}` is not an administrator of `{tournament.info.name}`"
                )
            tournament.administrator_roles.remove(role.name)

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})

        return (
            f"Role `{role.name}` successfully removed from "
            f"tournament `{tournament.info.name}`"
        )

    @arg_botcmd("team_name", type=str, nargs="+")
    @arg_botcmd("tournament_id", type=int)
    def register(self, msg: Message, tournament_id: int, team_name: List[str]):
        """ Todo: handle duplicates """
        if tournament_id not in self["tournaments"]:
            return "Tournament not found"

        team_name = " ".join(team_name)
        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])
            participant = tournament.find_team_by_name(team_name)
            if not participant:
                return (
                    f"Team {team_name} not found in the tournament {tournament.info.name}"
                )

            if participant.captain is not None:
                if participant.captain == msg.frm.fullname:
                    return (
                        f"You are already the captain of the team "
                        f"`{team_name}` for this tournament"
                    )
                else:
                    return (
                        f"Team `{team_name}` is already registered with the "
                        f"captain `{participant.captain}`"
                    )

            participant.captain = msg.frm.fullname

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})
            return (
                f"You are now the captain of the team `{team_name}` and "
                f"successfully checked-in for this tournament!"
            )

    @arg_botcmd("team_name", type=str, nargs="+")
    @arg_botcmd("tournament_id", type=int)
    def unregister(self, msg: Message, tournament_id: int, team_name: List[str]):
        """ TODO: Swap captains instead """
        if tournament_id not in self["tournaments"]:
            return "Tournament not found"

        team_name = " ".join(team_name)
        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])
            participant = tournament.find_team_by_name(team_name)
            if not participant:
                return (
                    f"Team {team_name} not found in the tournament {tournament.info.name}"
                )

            if msg.frm.fullname != participant.captain:
                return (
                    f"Team `{participant.name}` not linked to your account. "
                    f"The team captain is `{participant.captain}`"
                )

            participant.captain = None

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})
            return f"Team `{participant.name}` successfully unlinked with your account"

    @botcmd
    def show_status(self, msg, args):
        for tournament_dict in self["tournaments"].values():
            tournament = Tournament.from_dict(tournament_dict)

            participant = tournament.find_team_by_captain(msg.frm.fullname)
            if participant:
                self.send_card(
                    title=f"{tournament.info.name} " f"({tournament.tournament_id})",
                    body=f"**Team ID:** {participant.id}\n"
                    f"**Team Name:** {participant.name}\n"
                    f"**Team Captain:** {participant.captain}\n"
                    f"**Team Players:** "
                    + ", ".join(pl.name for pl in participant.lineup),
                    summary=f"To unregister, type:\n"
                    f"!unregister "
                    f"{tournament.tournament_id} "
                    f"{participant.name}",
                    in_reply_to=msg,
                )

    @arg_botcmd("tournament_id", type=int)
    def show_registered_teams(self, msg: Message, tournament_id):
        if tournament_id not in self["tournaments"]:
            return "Tournament doesn't exists"

        tournament = Tournament.from_dict(self["tournaments"][tournament_id])
        participants = sorted(tournament.teams, key=lambda k: getattr(k, "name"))
        participants = [p for p in participants if p.captain is not None]
        if len(participants) == 0:
            return "No team registered for this tournament"

        count = 1
        participants_chunks = self.chunks(participants, 100)
        for i, chunk in enumerate(participants_chunks):
            team_names = ""
            for team in chunk:
                team_names += f"{count}. {team.name}\n"
                count += 1

            self.send_card(
                title=f"{tournament.info.name} Registered Participants"
                f"({i + 1}/{len(participants_chunks)})",
                body=(
                    f"Number of teams: "
                    f"{len(tournament.teams)} \n"
                    f"Number of registrations: "
                    f"{tournament.count_registered_participants()}\n\n"
                    f"{team_names}"
                ),
                color="green",
                in_reply_to=msg,
            )

    @arg_botcmd("tournament_id", type=int)
    def show_unregistered_teams(self, msg: Message, tournament_id):
        if tournament_id not in self["tournaments"]:
            return "Tournament doesn't exists"

        tournament = Tournament.from_dict(self["tournaments"][tournament_id])
        participants = sorted(tournament.teams, key=lambda k: getattr(k, "name"))
        participants = [p for p in participants if p.captain is None]
        if len(participants) == 0:
            return "Every team registered for this tournament"

        missing_participants_count = (
            len(tournament.teams) - tournament.count_registered_participants()
        )
        count = 1
        participants_chunks = self.chunks(participants, 100)
        for i, chunk in enumerate(participants_chunks):
            team_names = ""
            for team in chunk:
                team_names += f"{count}. {team.name}\n"
                count += 1

            self.send_card(
                title=f"{tournament.info.name} Missing Registrations "
                f"({i + 1}/{len(participants_chunks)})",
                body=(
                    f"Number of teams: "
                    f"{len(tournament.teams)} \n"
                    f"Number of missing registrations: "
                    f"{missing_participants_count}\n\n"
                    f"{team_names}"
                ),
                color="green",
                in_reply_to=msg,
            )

    @arg_botcmd("match_name", type=str)
    @arg_botcmd("tournament_id", type=int)
    def create_match(self, msg, tournament_id, match_name):
        if not self.is_tournament_admin(msg.frm, tournament_id):
            return "You are not allowed to perform this action"

        if tournament_id not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])
            match = tournament.find_match_by_name(match_name)
            if match:
                return "Match name already exists"

            tournament.matches.append(Match(name=match_name, created_by=msg.frm.fullname))

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})
            return f"Match `{match_name}` successfully created."

    @arg_botcmd("tournament_id", type=int)
    def get_matches(self, msg, tournament_id):
        if tournament_id not in self["tournaments"]:
            return "Tournament not found"

        tournament = Tournament.from_dict(self["tournaments"][tournament_id])
        self.send_card(
            title=tournament.info.name,
            fields=(
                *(
                    (
                        str(match.name),
                        f"**Status:** {match.status.name}\n"
                        f"**Teams Ready:** {len(match.teams_ready)}/"
                        f"{tournament.count_registered_participants()}\n"
                        f"**Created by:** {match.created_by}\n",
                    )
                    for match in tournament.matches
                ),
            ),
            in_reply_to=msg,
        )

    @arg_botcmd("match_name", type=str, help="Name of the match to join")
    @arg_botcmd("tournament_id", type=int)
    def ready(self, msg: Message, tournament_id: int, match_name: str):
        if tournament_id not in self["tournaments"]:
            return "Tournament not found."

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])
            match = tournament.find_match_by_name(match_name)
            if not match:
                return "Match not found"

            team = tournament.find_team_by_captain(msg.frm.fullname)
            if not team:
                return "You are not captain of a team in this tournament"

            if match.find_team_by_name(team.name):
                return f"Team `{team.name}` is already ready for this match"

            if match.status != MatchStatus.PENDING:
                return f"Can't join match with status {match.status.name}"

            match.teams_ready.append(team)

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})
            return f"Team `{team.name}` is now ready for the match {match_name}!"

    @arg_botcmd("match_name", type=str, help="Name of the match to join")
    @arg_botcmd("tournament_id", type=int)
    def start_match(self, msg, tournament_id: int, match_name: str):
        if not self.is_tournament_admin(msg.frm, tournament_id):
            return "You are not allowed to perform this action"

        if tournament_id not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])
            match = tournament.find_match_by_name(match_name)
            if not match:
                return "Match not found"
            if match.status != MatchStatus.PENDING:
                return f"Can't start match with status {match.status.name}"

            for channel in tournament.channels:
                room = self.query_room(channel)
                self.send(room, f"The match `{match_name}` will start in ~30 seconds!")

            for team in match.teams_ready:
                captain_user = self.build_identifier(team.captain)
                self.send(
                    captain_user,
                    f"The match `{match_name}` for the team `{team.name}` "
                    f"will start in ~30 seconds!",
                )

            match.status = MatchStatus.ONGOING

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})
            self.send(msg.frm, f"Match `{match_name}` status set to ONGOING.")

    @arg_botcmd("match_name", type=str, help="Name of the match to join")
    @arg_botcmd("tournament_id", type=int)
    def end_match(self, msg, tournament_id: int, match_name: str):
        if not self.is_tournament_admin(msg.frm, tournament_id):
            return "You are not allowed to perform this action"

        if tournament_id not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[tournament_id])
            match = tournament.find_match_by_name(match_name)
            if match:
                return "Match name already exists"
            if match.status != MatchStatus.ONGOING:
                return f"Can't end match with status `{match.status.name}`"

            match.status = MatchStatus.COMPLETED

            # Save tournament changes to db
            tournaments.update({tournament_id: tournament.to_dict()})
            return self.send(msg.frm, f"Match `{match_name}` status set to COMPLETED.")

    def _send_tournament_info(self, msg, tournament: Tournament):
        team_status_text = "**You are not the captain of any team in this tournament*"
        team = tournament.find_team_by_captain(msg.frm.fullname)
        if team is not None:
            team_players = ", ".join(pl.name for pl in team.lineup) or None
            team_status_text = (
                f"**Team Name:** {team.name}\n" f"**Team Players:** {team_players}"
            )

        administrators = []
        for admin_role in tournament.administrator_roles:
            administrators.extend(self._bot.get_role_members(admin_role))
        admins = ", ".join(administrators)

        self.send_card(
            title=tournament.info.name,
            link=tournament.url,
            body=f"{tournament.url}\n\n{team_status_text}",
            summary=f"Tournament Administrators:\t{admins}",
            fields=(
                ("Tournament ID", str(tournament.info.id)),
                ("Participants", str(len(tournament.teams))),
                (
                    "Registered Participants",
                    str(tournament.count_registered_participants()),
                ),
                ("Default channels", "\n".join(tournament.channels) or None),
                ("Game", tournament.info.discipline),
            ),
            color="green" if team else "red",
            in_reply_to=msg,
        )

    @staticmethod
    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        return list(l[i : i + n] for i in range(0, len(l), n))

    def is_tournament_admin(self, user: DiscordPerson, tournament_id) -> bool:
        if tournament_id not in self["tournaments"]:
            logger.error("Tournament not found")
            return False

        tournament = Tournament.from_dict(self["tournaments"][tournament_id])
        return any(user.has_guild_role(r) for r in tournament.administrator_roles)
