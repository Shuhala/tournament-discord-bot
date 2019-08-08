import logging
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
        print('Received a Discord message with attachemnts')

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
                tournament = {}

                # Toornament data
                tournament_info = self.toornament_api_client.get_tournament(tournament_id)
                if not tournament_info:
                    return "Tournament not found."

                participants = self.toornament_api_client.get_participants(tournament_id)
                tournament_info.update({"participants": participants})

                tournament.update({"info": tournament_info})

                # Application data
                tournament.setdefault("administrators", roles)
                tournament.setdefault("channels", channels)
                tournament.setdefault("registrations", [])
                tournament.setdefault("matches", [])
                tournament.update(
                    {
                        "url": f"https://www.toornament.com/en_US/tournaments/"
                        f"{tournament_id}/information"
                    }
                )

                # Add to tournaments
                tournaments.update({tournament_id: tournament})
                return f"Tournament '{tournament['info']['name']}' successfully added"

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
        with self.mutable("tournaments") as tournaments:
            tournament = tournaments.get(tournament_id)
            if not tournament:
                return "Tournament not found"

            if channels:
                tournament["channels"].extend(channels)

            if roles:
                tournament["administrators"].extend(roles)

    @arg_botcmd("tournament_id", type=int)
    def refresh_tournament(self, msg: Message, tournament_id: int):
        """ Refresh a tournament information """
        with self.mutable("tournaments") as tournaments:
            if tournament_id not in tournaments:
                return "Tournament not found. Has it been added first?"

            tournament_info = tournaments[tournament_id]["info"]

            # update data fetched on Toornament
            result = self.toornament_api_client.get_tournament(tournament_id)
            if not result:
                return "Tournament not found on Toornament."
            tournament_info.update(result)

            # update participants list
            participants = self.toornament_api_client.get_participants(tournament_id)
            tournament_info.update({"participants": participants})

            # refresh administrators
            for admin in tournaments[tournament_id]["administrators"]:
                role = self._bot.find_role(admin["role"])
                if not role:
                    logger.error("Role not found")
                    return

                for member in role.members:
                    admin["members"].add(str(member))

    @arg_botcmd("tournament_id", type=int)
    def get_tournament(self, msg, tournament_id):
        if tournament_id not in self["tournaments"]:
            return "Tournament not found."

        tournament = self["tournaments"][tournament_id]
        self._send_tournament_info(msg, tournament)

    @botcmd
    def get_tournaments(self, msg, args):
        for tournament in self["tournaments"].values():
            self._send_tournament_info(msg, tournament)

    @arg_botcmd("discord_role", type=str)
    @arg_botcmd("tournament_id", type=int)
    def add_role(self, msg, tournament_id, discord_role):
        """ Associate a Discord role to a tournament """
        role = self._bot.find_role(discord_role)
        if not role:
            return f"Role '{discord_role}' not found"

        with self.mutable("tournaments") as tournaments:
            tournament = tournaments.get(tournament_id)
            if not tournament:
                return f"Tournament '{tournament_id}' not found."

            admin = get_tournament_administrator_by(tournament, "role", role.name)
            if admin:
                return (
                    f"{role.name} is already a tournament administrator role "
                    f"of '{tournament['info']['name']}'"
                )

            tournament["administrators"].append(
                {"role": role.name, "members": set(str(m) for m in role.members)}
            )

        return (
            f"Administrator role '{role.name}' added to "
            f"tournament '{tournament['info']['name']}'"
        )

    @arg_botcmd("discord_role", type=str)
    @arg_botcmd("tournament_id", type=int)
    def remove_role(self, msg, tournament_id, discord_role):
        """ Remove an associated Discord role from a tournament """
        role = self._bot.find_role(discord_role)
        if not role:
            return f"Role '{discord_role}' not found"

        with self.mutable("tournaments") as tournaments:
            tournament = tournaments.get(tournament_id)
            if not tournament:
                return f"Tournament '{tournament_id}' not found."

            if role.name not in tournament["administrators"]:
                return f"{role.name} is not an administrator of '{tournament['name']}'"

            tournament["administrators"].pop(role.name)

        return (
            f"Administrator role '{role.name}' successfully removed from "
            f"tournament '{tournament['name']}'"
        )

    @arg_botcmd("team_name", type=str, nargs="+")
    @arg_botcmd("tournament_id", type=int)
    def register(self, msg: Message, tournament_id: int, team_name: List[str]):
        """ Todo: handle duplicates """
        team_name = " ".join(team_name)

        with self.mutable("tournaments") as tournaments:
            tournament = tournaments.get(tournament_id)
            if not tournament:
                return f"No tournament found with the ID '{tournament_id}'"

            participant = get_tournament_participant_by(tournament, "name", team_name)
            if not participant:
                return (
                    f"Team '{team_name}' not found in "
                    f"the participants list for this tournament"
                )

            registration = get_tournament_registration_by(
                tournament, "captain", msg.frm.fullname
            )
            if registration:
                return (
                    f"You are already the captain of the team "
                    f"'{registration['name']}' in this tournament"
                )

            registration = get_tournament_registration_by(
                tournament, "id", participant["id"]
            )
            if registration:
                return (
                    f"Team '{team_name}' already registered with the "
                    f"captain {registration['captain']}"
                )

            tournament["registrations"].append(
                {
                    "id": participant["id"],
                    "name": participant["name"],
                    "captain": msg.frm.fullname,
                }
            )

            return f"Team '{team_name}' successfully registered for this tournament!"

    @arg_botcmd("registration_id", type=str)
    @arg_botcmd("tournament_id", type=int)
    def unregister(self, msg: Message, tournament_id: int, registration_id: str):
        """ TODO: Swap captains instead """
        with self.mutable("tournaments") as tournaments:
            tournament = tournaments.get(tournament_id)
            if not tournament:
                return "Tournament not found."

            registration = get_tournament_registration_by(
                tournament, "id", registration_id
            )
            if not registration:
                return (
                    f"No registration found for '{tournament['name']}' with "
                    f"the id {registration_id}"
                )

            if msg.frm.fullname != registration["captain"]:
                return (
                    f"Team '{registration['name']}' not linked to your account. "
                    f"The team captain is '{registration['captain']}'"
                )

            registration["captain"] = None

            return (
                f"Team '{registration['name']}' successfully unlinked with your account "
            )

    @botcmd
    def get_registrations(self, msg, args):
        for tournament in self["tournaments"].values():
            for registration in tournament["registrations"]:
                if msg.frm.fullname == registration["captain"]:
                    participant = get_tournament_participant_by(
                        tournament, "id", registration["id"]
                    )
                    self.send_card(
                        title=f"{tournament['info']['name']} "
                        f"({tournament['info']['id']})",
                        fields=(
                            ("ID", registration["id"]),
                            ("Team", registration["name"]),
                            (
                                "Players",
                                "\n".join(l["name"] for l in participant["lineup"])
                                if participant
                                else None,
                            ),
                        ),
                        summary=f"!unregister "
                        f"{tournament['info']['id']} "
                        f"{registration['id']}",
                        in_reply_to=msg,
                    )

    @arg_botcmd("tournament_id", type=int)
    def get_registered_teams(self, msg: Message, tournament_id):
        if tournament_id not in self["tournaments"]:
            return "Tournament doesn't exists"

        tournament = self["tournaments"][tournament_id]

        registrations = sorted(tournament["registrations"], key=lambda k: k["name"])
        registrations_chunks = self.chunks(registrations, 100)

        for count, chunk in enumerate(registrations_chunks):
            self.send_card(
                title=f"{tournament['info']['name']} Registrations "
                f"({count + 1}/{len(registrations_chunks)})",
                body=(
                    f"Number of participants: "
                    f"{len(tournament['info']['participants'])} \n"
                    f"Number of registrations: "
                    f"{len(registrations)}\n\n"
                    + f"\n ".join(f"{i + 1}) {p['name']}" for i, p in enumerate(chunk))
                ),
                color="green",
                in_reply_to=msg,
            )

    @arg_botcmd("tournament_id", type=int)
    def get_unregistered_teams(self, msg: Message, tournament_id):
        if tournament_id not in self["tournaments"]:
            return "Tournament doesn't exists"

        tournament = self["tournaments"][tournament_id]

        unregistered_participants = [
            p
            for p in tournament["info"]["participants"]
            if not any(p["id"] == r["id"] for r in tournament["registrations"])
        ]
        registrations = sorted(unregistered_participants, key=lambda k: k["name"])
        registrations_chunks = self.chunks(registrations, 100)

        for count, chunk in enumerate(registrations_chunks):
            self.send_card(
                title=f"{tournament['info']['name']} Missing Registrations "
                f"({count + 1}/{len(registrations_chunks)})",
                body=(
                    f"Number of participants: "
                    f"{len(tournament['info']['participants'])} \n"
                    f"Number of missing registrations: "
                    f"{len(unregistered_participants)}\n\n"
                    + f"\n ".join(f"{i + 1}) {p['name']}" for i, p in enumerate(chunk))
                ),
                color="green",
                in_reply_to=msg,
            )

    @arg_botcmd("match_name", type=str)
    @arg_botcmd("tournament_id", type=int)
    def create_match(self, msg, tournament_id, match_name):
        if not self.is_tournament_admin(msg.frm, tournament_id):
            return "You don't have the right to execute this command"

        if tournament_id not in self["tournaments"]:
            return "Tournament doesn't exists"

        with self.mutable("tournaments") as tournaments:
            match = get_tournament_match_by(
                tournaments[tournament_id], "name", match_name
            )
            if match:
                return "Match name already exists"

            tournaments[tournament_id]["matches"].append(
                {
                    "name": match_name,
                    "status": MatchStatus.PENDING,
                    "checked_in": [],
                    "created_by": msg.frm.fullname,
                }
            )

            return f"Match '{match_name}' successfully created."

    @arg_botcmd("tournament_id", type=int)
    def get_matches(self, msg, tournament_id):
        if tournament_id not in self["tournaments"]:
            return "Tournament doens't exists"

        tournament = self["tournaments"][tournament_id]
        self.send_card(
            title=tournament["info"]["name"],
            fields=(
                *(
                    (
                        str(match["name"]),
                        f"**Status** {match['status'].name}\n"
                        f"**Checked in** {len(match['checked_in'])}\n"
                        f"**Created by** {match['created_by']}\n",
                    )
                    for match in tournament["matches"]
                ),
            ),
            in_reply_to=msg,
        )

    @arg_botcmd("match_name", type=str, help="Name of the match to join")
    @arg_botcmd("tournament_id", type=int)
    def ready(self, msg: Message, tournament_id: int, match_name: str):
        if tournament_id not in self["tournaments"]:
            return "Tournament doens't exists"

        with self.mutable("tournaments") as tournaments:
            tournament = tournaments[tournament_id]
            match = get_tournament_match_by(tournament, "name", match_name)
            if not match:
                return "Match not found"

            team = get_tournament_registration_by(tournament, "captain", msg.frm.fullname)
            if not team:
                return "Team not found"

            if team["id"] in match["checked_in"]:
                return f"Team '{team['name']}' already checked in"

            if match["status"] != MatchStatus.PENDING:
                return f"Can't join match in status {match['status'].name}"

            match["checked_in"].append(team["id"])

            return f"Team '{team['name']}' successfully registered."

    @arg_botcmd("match_name", type=str, help="Name of the match to join")
    @arg_botcmd("tournament_id", type=int)
    def start_match(self, msg, tournament_id: int, match_name: str):
        if not self.is_tournament_admin(msg.frm, tournament_id):
            return "You are not allowed to perform this action"

        if tournament_id not in self["tournaments"]:
            return "Tournament doens't exists"

        with self.mutable("tournaments") as tournaments:
            tournament = tournaments[tournament_id]
            match = get_tournament_match_by(tournament, "name", match_name)
            if not match:
                return "Match not found"

            if match["status"] != MatchStatus.PENDING:
                return "Can't start this match"

            if tournament["channels"]:
                for channel in tournament["channels"]:
                    room = self.build_identifier(channel)
                    self.send(room, f"Match '{match_name}' will start in 30 seconds")

            # for team, captain in match.get('checked_in').items():
            #     captain_user = self.build_identifier(captain)
            #     self.send(
            #         captain_user, 'The match {} for the team
            # {} will start in ~30seconds.'.format(match_name, team)
            #     )
            match["status"] = MatchStatus.ONGOING

            self.send(msg.frm, f"Match '{match_name}' status set to ONGOING.")

    @arg_botcmd("match_name", type=str, help="Name of the match to join")
    @arg_botcmd("tournament_id", type=int)
    def end_match(self, msg, tournament_id: int, match_name: str):
        if not self.is_tournament_admin(msg.frm, tournament_id):
            return "You are not allowed to perform this action"

        if tournament_id not in self["tournaments"]:
            return "Tournament doens't exists"

        with self.mutable("tournaments") as tournaments:
            tournament = tournaments[tournament_id]
            match = get_tournament_match_by(tournament, "name", match_name)
            if not match:
                return "Match not found"

            if match["status"] != MatchStatus.ONGOING:
                return "Can't end this match"

            match["status"] = MatchStatus.COMPLETED
            return self.send(
                msg.frm, "Match '{}' status set to COMPLETED.".format(match_name)
            )

    def _send_tournament_info(self, msg, tournament):
        registration = get_tournament_registration_by(
            tournament, "captain", msg.frm.fullname
        )

        team_status_text = "**You are not the captain of any team in this tournament*"
        if registration:
            participants = get_tournament_participant_by(
                tournament, "id", registration["id"]
            )
            team_players = ", ".join(l["name"] for l in participants["lineup"]) or None
            team_status_text = (
                f"**Team Name:** {registration['name']}\n"
                f"**Team Players:** {team_players}"
            )

        admins = ", ".join(get_tournament_administrator_members(tournament))
        self.send_card(
            title=tournament["info"]["name"],
            link=tournament["url"],
            body=f"{tournament['url']}\n\n{team_status_text}",
            summary=f"Tournament Administrators:\t{admins}",
            fields=(
                ("ID", tournament["info"]["id"]),
                ("Participants", str(len(tournament["info"]["participants"]))),
                ("Checked-in", str(len(tournament["registrations"]))),
                ("Default channels", "\n".join(tournament["channels"]) or None),
                ("Game", tournament["info"]["discipline"]),
                # ("Prize", tournament["info"]["prize"]),
            ),
            color="green" if registration else "red",
            in_reply_to=msg,
        )

    @staticmethod
    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        return list(l[i : i + n] for i in range(0, len(l), n))

    def is_tournament_admin(self, user: DiscordPerson, tournament_id) -> bool:
        if tournament_id not in self["tournaments"]:
            logger.error("Tournament doesn't exists")
            return False

        tournament_administrators = self["tournaments"][tournament_id]["administrators"]
        return any(user.has_guild_role(r["role"]) for r in tournament_administrators)
