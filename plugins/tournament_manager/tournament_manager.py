import csv
import itertools
import logging
import os
import tempfile
from datetime import datetime
from time import sleep
from typing import Optional, List, Tuple

import discord
from errbot import BotPlugin, botcmd, Message, arg_botcmd

from backends.discord.discord import DiscordPerson
from plugins.tournament_manager.clients.toornament_api_client import ToornamentAPIClient
from plugins.tournament_manager.decorators import (
    private_message_only,
    tournament_channel_only,
    tournament_admin_only,
)
from plugins.tournament_manager.models import (
    Match,
    MatchStatus,
    Player,
    ScoreSubmission,
    Team,
    ToornamentInfo,
    Tournament,
)
from plugins.tournament_manager.utils.chunks import chunks

logger = logging.getLogger(__name__)


class TournamentManagerPlugin(BotPlugin):
    toornament_api_client = None

    def activate(self):
        """ Triggers on plugin activation """
        super(TournamentManagerPlugin, self).activate()
        self.toornament_api_client = ToornamentAPIClient()
        if "tournaments" not in self:
            self["tournaments"] = {}

    @botcmd
    @private_message_only
    def help(self, msg, *args):
        """ Display bot commands """

        # Sketchy override of the bot help command

        def sanitize_cmd(cmd_text: str):
            return " ".join(l.strip() for l in cmd_text.split("\n"))

        commands = []
        linked_commands = []
        admin_commands = []
        for cmd_name, cmd in self._bot.commands.items():
            # Extract command names and descriptions
            if not hasattr(cmd, "_err_command_parser"):
                # undocumented
                description = sanitize_cmd(self._bot.get_doc(cmd))
                name = cmd_name
            elif cmd._err_command_parser.description:
                # use command docstring
                description = sanitize_cmd(cmd._err_command_parser.description)
                name = (
                    cmd_name
                    + " "
                    + " ".join(
                        f"*[{a.dest}]*" for a in cmd._err_command_parser._actions[1:]
                    )
                )
            else:
                # use argparse syntax
                description = cmd._err_command_syntax
                name = (
                    cmd_name
                    + " "
                    + " ".join(
                        f"*[{a.dest}]*" for a in cmd._err_command_parser._actions[1:]
                    )
                )

            if "[ADMIN]" in description.upper():
                admin_commands.append((name, description))
            elif "[LINKED]" in description.upper():
                linked_commands.append((name, description))
            else:
                commands.append((name, description))

        # General Commands
        help_message = (
            "```General Commands```"
            "*Bot available commands. "
            "\nNote: The **[alias]** parameter is the `Tournament Alias` field that can "
            "be found in the tournaments description. To see available tournaments, "
            "use `!show tournaments`*"
            "\n\n"
        )
        help_message += "\n\n".join(f"**!{name}**\n{descr}" for name, descr in commands)
        self.send(msg.frm, help_message)

        # Linked Commands
        help_message = (
            f"```Linked Captains Commands```"
            f"*Commands available to captains linked to a team*\n\n"
        )
        help_message += "\n\n".join(
            f"**!{name}**\n{descr[10:]}" for name, descr in linked_commands
        )
        help_message += (
            "\n\n**!submit *[match_name]* position *[number]* eliminations *[number]***"
            "\n***THIS COMMAND MUST BE SENT IN PRIVATE TO THE BOT WITH A SCREENSHOT "
            "ATTACHED TO IT***\n"
            "Submit your team score for a match. "
            "E.g. with an attached screenshot, add the message: `!submit game_1 position "
            "2 eliminations 5` to submit a score where your position is `2`nd and number "
            "of eliminations `5` for the match named `game_1`.\n"
            "- Score submission is disabled when a match status is set to COMPLETED.\n"
            "- If you made a mistake while submitting your score, use this command "
            "again to override the previous submission for this match.\n"
            "- The information submitted must match the one visible on your screenshot. "
            "Submitting a different score than what is displayed on your screenshot "
            "will result in a sanction.\n"
        )
        self.send(msg.frm, help_message)

        # Admin Commands
        if self._is_tournament_admin(msg.frm):
            help_message = "```Admin Commands```\n"
            help_message += "\n\n".join(
                f"**!{name}**\n{descr[9:]}" for name, descr in admin_commands
            )
            self.send(msg.frm, help_message)

        self.send(
            msg.frm,
            "Commands summary are also available at this link: "
            "<https://docs.google.com/document/d/1eedLoQdVLVe2JkCe19g69w-UUL49iFW93mz4piypY1k/edit?usp=sharing>",
            # noqa
        )

    @arg_botcmd("role", type=str, nargs="+")
    @arg_botcmd("alias", type=str, admin_only=True)
    @tournament_admin_only
    def add_admin_role(self, msg, alias: str, role: List[str]):
        """
        [Admin] Link a Discord admin role to a tournament.
        E.g. `!add admin role fortnite Fortnite Admin`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found."

        role = " ".join(role)
        if not self._bot.find_role(role):
            return f"Role `{role}` not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])

            if role in tournament.administrator_roles:
                return (
                    f"Role `{role}` is already a tournament administrator role "
                    f"of `{tournament.alias}`"
                )
            tournament.administrator_roles.append(role)

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return (
                f"Role `{role}` successfully added "
                f"to the tournament `{tournament.alias}`"
            )

    @arg_botcmd("role", type=str, nargs="+")
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def add_captain_role(self, msg, alias: str, role: List[str]):
        """
        [Admin] Link a Discord role as a tournament Captain role.
        Players that will link their Discord account with their team for this tournament
        will also be assigned the Captain role.
        E.g. `!add captain fortnite Fortnite Captain`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found."

        role = " ".join(role)
        if not self._bot.find_role(role):
            return f"Role `{role}` not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            tournament.captain_role = role

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return (
                f"Captain role `{role}` successfully added "
                f"to the tournament `{tournament.alias}`"
            )

    @arg_botcmd("channel", type=str)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def add_channel(self, msg, alias, channel):
        """
        [Admin] Link a Discord channel to a tournament.
        E.g. `!add channel fortnite #fortnite-tournament`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found."

        if not self.query_room(channel):
            return "Invalid channel name"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])

            if channel in tournament.channels:
                return (
                    f"Channel `{channel}` is already set for the tournament "
                    f"`{tournament.alias}`"
                )
            tournament.channels.append(channel)

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return f"Channels successfully added to the tournament"

    @arg_botcmd("tournament_id", type=int)
    @arg_botcmd("alias", type=str, admin_only=True)
    @tournament_admin_only
    def add_tournament(self, msg: Message, alias, tournament_id: int):
        """
        [Admin] `!add tournament fortnite 123456789`
        """
        with self.mutable("tournaments") as tournaments:
            if alias in tournaments:
                return "Tournament with this alias already exists."

            tournament = Tournament(
                id=tournament_id,
                alias=alias,
                url=f"https://www.toornament.com/en_US/tournaments/"
                f"{tournament_id}/information",
            )

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
            tournaments.update({alias: tournament.to_dict()})
            self.send(msg.frm, f"Tournament `{tournament.info.name}` successfully added")

    def callback_attachment(self, msg: Message, discord_msg: discord.Message):
        """ Send screenshots in private message to bot """
        if hasattr(msg.to, "fullname") and msg.to.fullname == str(self.bot_identifier):
            cmds = ["!submit", "!add", "!add_screenshot"]
            msg_parts = msg.body.strip().split(" ")

            if not msg_parts or msg_parts[0] not in cmds:
                self.send(
                    msg.frm,
                    (
                        "Wow! Thank you so much for this beautiful attachment!\n"
                        "Unfortunately, I'm unsure what I'm supposed to do with that."
                        " Are you trying to submit a match score screenshot?\n"
                        "To submit a score for a match, use: "
                        "`submit [match_name] position [number] eliminations [number]`.\n"
                        "To add a screenshot to your previous score submission, use: "
                        "`!add screenshot [match_name]`.\n"
                        "To remove a score submission for a match and add a new one, use "
                        "`!remove score [match_name]`."
                    ),
                )
                return

            with self.mutable("tournaments") as tournaments:
                team, tournament = self._find_captain_team(msg.frm.fullname, tournaments)
                if not team:
                    self.send(msg.frm, "You are not the captain of a team.")
                    return

                # !submit
                if msg_parts[0] == "!submit":

                    # invalid format
                    if len(msg_parts) != 6:
                        self.send(
                            msg.frm,
                            (
                                "Looks like you're trying to submit your score!\n\n"
                                "Your screenshot must be followed with the following"
                                " information: "
                                "`!submit [match_name] position [number] "
                                "eliminations [number]`\n"
                            ),
                        )
                        return

                    _, match_name, _, position, _, eliminations = msg_parts
                    match = tournament.find_match_by_name(match_name)

                    # match not found
                    if not match:
                        self.send(
                            msg.frm,
                            f"There is no match with the name `{match_name}` for "
                            f"the `{tournament.alias}` tournament. Can't submit "
                            f"score.",
                        )
                        return
                    # Team not registered in this game
                    if match.id and team.id not in match.teams_registered:
                        self.send(
                            msg.frm,
                            "You are not authorized to submit a score for this match, "
                            f"your team is not registered in this match group "
                            f"`{match.group_name}`",
                        )
                    # invalid entries
                    if not position.isdigit() or not eliminations.isdigit():
                        self.send(
                            msg.frm,
                            "Invalid entry for position or eliminations. "
                            "A number was expected.",
                        )
                        return
                    # match completed, submissions locked
                    if match.status == MatchStatus.COMPLETED:
                        self.send(
                            msg.frm,
                            f"Can't submit score for the match `{match_name}`. "
                            f"Match status is set to COMPLETED. "
                            f"Submissions are now locked. "
                            f"Please contact your Tournament Administrator.",
                        )
                        return
                    # score already submitted
                    score = team.find_submission_by_match(match_name)
                    if score:
                        self.send(
                            msg.frm,
                            f"Score for the match `{match_name}` already submitted.\n"
                            f"Use `!remove score [match_name]` if you want to submit "
                            f"a different score, or `!add screenshot [match_name]` to "
                            f"add a screenshot to your submission.",
                        )
                        return

                    # add score
                    score = ScoreSubmission(
                        match_name=match_name,
                        team_name=team.name,
                        screenshot_links=[a.url for a in discord_msg.attachments],
                        position=int(position),
                        eliminations=int(eliminations),
                    )
                    team.score_submissions.append(score)
                    self.send(
                        msg.frm,
                        "Score successfully added! Type `!show scores` "
                        "to see your score submissions history.",
                    )
                    tournaments.update({tournament.alias: tournament.to_dict()})

                # add screenshot
                elif (msg_parts[0] == "!add" and msg_parts[1] == "screenshot") or (
                    msg_parts[0] == "!add_screenshot"
                ):
                    if len(msg_parts) == 3:
                        match_name = msg_parts[2]
                    elif len(msg_parts) == 2:
                        match_name = msg_parts[1]
                    else:
                        self.send(
                            msg.frm,
                            "Invalid command format. Use `!add screenshot [match_name]`",
                        )
                        return

                    match = tournament.find_match_by_name(match_name)

                    # match not found
                    if not match:
                        self.send(
                            msg.frm,
                            f"There is no match with the name `{match_name}` for "
                            f"the `{tournament.alias}` tournament. Can't submit "
                            f"score.",
                        )
                        return
                    # match completed, submissions locked
                    if match.status == MatchStatus.COMPLETED:
                        self.send(
                            msg.frm,
                            f"Can't submit score for the match `{match_name}`. "
                            f"Match status is set to COMPLETED. "
                            f"Submissions are now locked. "
                            f"Please contact your Tournament Administrator.",
                        )
                        return

                    # update score
                    score = team.find_submission_by_match(match_name)
                    if not score:
                        self.send(
                            msg.frm,
                            f"No score submission found for the match `{match_name}`. "
                            "Use `!submit [match_name] position [number] "
                            "eliminations [number]` to submit your score.\n",
                        )
                    score.screenshot_links.extend(
                        [a.url for a in discord_msg.attachments]
                    )
                    score.updated_at = datetime.now().strftime("%m/%d/%Y %H:%M:%S")
                    self.send(
                        msg.frm,
                        "Score successfully updated! Type `!show score history` "
                        "to see your score submissions history.",
                    )
                    tournaments.update({tournament.alias: tournament.to_dict()})

    @arg_botcmd("match_id", type=int)
    @arg_botcmd("password", type=str)
    @arg_botcmd("match_name", type=str)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def create_match(self, msg, alias, match_name, password, match_id):
        """
        [Admin] Create a tournament match.
        E.g. `!create match fortnite match_1 secretPassword 123456789`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            match = tournament.find_match_by_name(match_name)
            if match:
                return "Match name already exists"

            match = Match(
                id=match_id,
                name=match_name,
                created_by=msg.frm.fullname,
                password=password,
            )

            if match_id:
                match_info = self.toornament_api_client.get_match(tournament.id, match_id)
                if not match_info:
                    return f"Match id `{match_id}` not found"
                match.group_name = match_info["public_notes"]
                match.teams_registered = [
                    p["participant"]["id"] for p in match_info["opponents"]
                ]

            tournament.matches.append(match)
            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})

            self.send(msg.frm, f"Match `{match_name}` successfully created.")
            self._show_match(msg, tournament, match)

    @arg_botcmd("match_name", type=str)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def download_match_scores(self, msg, alias: str, match_name: str):
        """
        [Admin] Download a match score submissions.
        E.g. `!download match scores fortnite match_1`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        tournament = Tournament.from_dict(self["tournaments"][alias])
        match = tournament.find_match_by_name(match_name)
        if not match:
            return f"Match `{match_name}` not found."

        match_scores = tournament.get_match_scores(match_name)
        if not match_scores:
            return "No score submissions found for this match."

        # create temporary csv to send
        fd, path = tempfile.mkstemp(
            prefix=f"{match_name}_scores_{datetime.now().strftime('%m-%d-%Y_%H-%M-%S')}_",
            suffix=".csv",
        )
        try:
            with open(path, "w") as csvfile:
                fw = csv.writer(csvfile, delimiter=",")
                fw.writerow(
                    [
                        "Team Name",
                        "Updated at",
                        "Position",
                        "Eliminations",
                        "Points",
                        "Screenshots",
                    ]
                )
                for ms in match_scores:
                    fw.writerow(
                        [
                            ms.team_name,
                            ms.updated_at,
                            ms.position,
                            ms.eliminations,
                            ms.count_points(),
                            " ".join(ms.screenshot_links),
                        ]
                    )
            self._bot.send_file(self.build_identifier(msg.frm.fullname), filepath=path)
        except Exception as e:
            logger.error(e)
            return f"Error: {e}"
        finally:
            os.remove(path)

    @arg_botcmd("--force", "-f", action="store_true")
    @arg_botcmd("match_name", type=str)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def end_match(self, msg, alias: str, match_name: str, force: bool):
        """
        [Admin] Set a tournament match status as completed. Players won't be able
        to update or send new score submissions for this match.
        E.g. `!end match fortnite match_1` or `!end match fortnite match_1 --force` to
        force to end the match what ever the match status is.
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            match = tournament.find_match_by_name(match_name)
            if not match:
                return "Match not found"
            if match.status != MatchStatus.ONGOING and not force:
                return f"Can't end match with status `{match.status.name}`"

            match.status = MatchStatus.COMPLETED

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return self.send(msg.frm, f"Match `{match_name}` status set to COMPLETED.")

    @arg_botcmd("match_name", type=str)
    @tournament_channel_only
    def join(self, msg: Message, match_name: str):
        """
        [Linked] Join a match.
        E.g. `!join match_1`
        """
        with self.mutable("tournaments") as tournaments:
            team, tournament = self._find_captain_team(msg.frm.fullname, tournaments)
            if not team:
                return "You are not a team captain."

            match = tournament.find_match_by_name(match_name)
            if not match:
                return "Match not found"

            if match.id and team.id not in match.teams_registered:
                return (
                    f"You are not authorized to join this match (ﾉ°□°)ﾉ ﾐ ┻━┻ !! "
                    f"Team `{team.name}` is not in this match group `{match.group_name}`"
                )

            if team.id in match.teams_joined:
                return f"Team `{team.name}` has already joined this match"

            if match.status != MatchStatus.PENDING:
                return f"Can't join match with status `{match.status.name}`"

            match.teams_joined.append(team.id)

            # Save tournament changes to db
            tournaments.update({tournament.alias: tournament.to_dict()})
            self.send(
                msg.frm, f"Team `{team.name}` is now ready for the match {match.name}!"
            )
            self._show_match(msg, tournament, match)

    @arg_botcmd("match_name", type=str)
    @tournament_channel_only
    def leave(self, msg: Message, match_name: str):
        """
        [Linked] Leave a joined match (if joined by mistake). Available when the match
        status is set to PENDING.
        E.g. `!leave match_1`
        """
        with self.mutable("tournaments") as tournaments:
            team, tournament = self._find_captain_team(msg.frm.fullname, tournaments)
            if not team:
                return "You are not a team captain."

            match = tournament.find_match_by_name(match_name)
            if not match:
                return "Match not found"

            if team.id not in match.teams_joined:
                return f"Team `{team.name}` is not in this match"

            if match.status != MatchStatus.PENDING:
                return f"Can't leave match with status `{match.status.name}`"

            match.teams_joined.remove(team.id)

            # Save tournament changes to db
            tournaments.update({tournament.alias: tournament.to_dict()})
            self.send(msg.frm, f"Team `{team.name}` has left the match `{match.name}`!")

    @arg_botcmd("team_name", type=str, nargs="+")
    @arg_botcmd("alias", type=str)
    @tournament_channel_only
    def link(self, msg: Message, alias: str, team_name: List[str]):
        """
        Link your Discord account with a team to become the captain of this team.
        If there is a quote (`'` or `"`) in your team name, add a backslash before: `\"`
        E.g. `!link fortnite Team Liquid`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        team_name = " ".join(team_name)
        with self.mutable("tournaments") as tournaments:
            team, tournament = self._find_captain_team(msg.frm.fullname, tournaments)
            if team:
                if team.name == team_name:
                    return "You are already linked to this team"
                return (
                    "You can't be the captain of more than one team.\n"
                    f"You are currently the captain of the team `{team.name}` for the "
                    f"tournament {tournament.name}"
                )

            tournament = Tournament.from_dict(tournaments[alias])
            team = tournament.find_team_by_name(team_name)
            if not team:
                return (
                    f"Team `{team_name}` not found in the tournament `{tournament.alias}`"
                )

            if team.captain is not None:
                return (
                    f"Team `{team_name}` is already registered to the "
                    f"captain `{team.captain}`"
                )

            team.captain = msg.frm.fullname

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})

            self._add_discord_team_captain(msg.frm, team_name, tournament.captain_role)

            return (
                f"You are now the captain of the team `{team_name}`. "
                f"Use `!show status` in private to display information about your team."
            )

    @arg_botcmd("discord_user", type=str, nargs="+")
    @arg_botcmd("team_id", type=int)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def link_team_captain(self, msg, alias: str, team_id: int, discord_user: str):
        """
        [Admin] Set a discord user as a team linked captain.
        E.g. `!link team captain fortnite 123456789 user#1234`
        """
        discord_user = " ".join(discord_user)
        if alias not in self["tournaments"]:
            return "Tournament not found"

        try:
            user = self.build_identifier(discord_user)
        except Exception:
            return f"User `{discord_user}` not found."

        if self._find_captain_team(discord_user, self["tournaments"])[0]:
            return f"User `{discord_user}` is already the captain of a team."

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            team = tournament.find_team_by_id(team_id)
            if not team:
                return (
                    f"Team `{team_id}` not found in the tournament `{tournament.alias}`"
                )

            if team.captain:
                self._remove_discord_team_captain(
                    self.build_identifier(team.captain), tournament.captain_role
                )

            team.captain = discord_user
            self._add_discord_team_captain(user, team.name, tournament.captain_role)

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return f"Team `{team.name}` captain successfully linked to `{discord_user}`."

    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def refresh_tournament(self, msg: Message, alias: str):
        """
        [Admin] Refresh a tournament's information.
        E.g. `!refresh tournament fortnite`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])

            # update data fetched on Toornament
            info = self.toornament_api_client.get_tournament(tournament.id)
            if not info:
                return "Tournament not found on Toornament."

            # Override current tournament info
            tournament.info = ToornamentInfo.from_dict(info)

            # update participants list
            participants = self.toornament_api_client.get_participants(tournament.id)
            for participant in participants:
                team = tournament.find_team_by_id(participant["id"])
                if team:
                    # Update participant name and lineup
                    team.name = participant["name"]
                    team.lineup = [Player(**pl) for pl in participant.get("lineup", [])]
                    team.checked_in = participant.get("checked_in")
                else:
                    # Add new participant
                    tournament.teams.append(Team.from_dict(participant))

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return f"Tournament {tournament.alias} successfully refreshed."

    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def show_tournament_refresh_status(self, msg: Message, alias: str):
        """
        [Admin] Show difference between current Tournament and
        Toornament participants list
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        # current tournament teams ids
        tournament = Tournament.from_dict(self["tournaments"][alias])
        tournament_team_ids = set(p.id for p in tournament.teams)
        # toornament participants ids
        participants = self.toornament_api_client.get_participants(tournament.id)
        toornament_participant_ids = set(p["id"] for p in participants)

        teams_deleted = tournament_team_ids - toornament_participant_ids
        teams_added = toornament_participant_ids - tournament_team_ids

        self.send(
            msg.frm, f"**Teams ID deleted:**\n" + "\n".join(i for i in teams_deleted)
        )
        self.send(msg.frm, f"**Teams ID added:**\n" + "\n".join(i for i in teams_added))

    @arg_botcmd("role", type=str, nargs="+")
    @arg_botcmd("alias", type=str, admin_only=True)
    @tournament_admin_only
    def remove_admin_role(self, msg, alias: str, role: List[str]):
        """
        [Admin] Remove a Discord admin role from a tournament.
        E.g. `!remove admin role fortnite Fortnite Admin`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found."

        role = " ".join(role)
        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])

            if role not in tournament.administrator_roles:
                return f"Role `{role.name}` is not a role of `{tournament.alias}`"
            tournament.administrator_roles.remove(role.name)

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return f"Roles successfully removed from the tournament `{tournament.alias}`"

    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def remove_captain_role(self, msg, alias):
        """ [Admin] Remove a tournament Discord Captain Role """
        if alias not in self["tournaments"]:
            return "Tournament not found."

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            tournament.captain_role = None

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return (
                f"Captain Role successfully removed for "
                f"the tournament `{tournament.alias}`"
            )

    @arg_botcmd("channel", type=str)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def remove_channel(self, msg, alias, channel):
        """
        [Admin] Remove a linked Discord channel from a tournament.
        E.g. !remove channel fornite #fortnite-tournament
        """
        if alias not in self["tournaments"]:
            return "Tournament not found."

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            if channel not in tournament.channels:
                return (
                    f"Channel `{channel}` doesn't exists for the tournament "
                    f"`{tournament.alias}`"
                )
            tournament.channels.remove(channel)

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return f"Channels successfully removed from the tournament"

    @arg_botcmd("match_name", type=str)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def remove_match(self, msg, alias, match_name):
        """
        [Admin] Remove a linked Discord channel from a tournament.
        E.g. !remove channel fornite #fortnite-tournament
        """
        if alias not in self["tournaments"]:
            return "Tournament not found."

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            match = tournament.find_match_by_name(match_name)
            if not match:
                return "Match not found"

            tournament.matches.remove(match)

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return f"Match `{match_name}` successfully removed from the tournament"

    @arg_botcmd("match_name", type=str)
    @private_message_only
    def remove_score(self, msg: Message, match_name: str):
        """
        [Linked] Remove a submitted match score.
        E.g. `!remove score match_1`
        """
        with self.mutable("tournaments") as tournaments:
            team, tournament = self._find_captain_team(msg.frm.fullname, tournaments)
            if not team:
                return "You are not a team captain."

            match = tournament.find_match_by_name(match_name)
            if not match:
                return f"Match `{match_name}` not found in `{tournament.alias}`"

            if match.status == MatchStatus.COMPLETED:
                return (
                    f"Can't delete score for match `{match_name}`. "
                    f"Match status is set to COMPLETED."
                )

            score = team.find_submission_by_match(match_name)
            if not score:
                return f"No score found for the match `{match_name}`"

            team.score_submissions.remove(score)

            # Save tournament changes to db
            tournaments.update({tournament.alias: tournament.to_dict()})
            return f"Score for match `{match_name}` successfully deleted."

    @arg_botcmd("team_id", type=int)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def remove_team(self, msg: Message, alias: str, team_id: int):
        """
        [Admin] Remove a team from a tournament.
        E.g. `!remove team fortnite 123456789`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            team = tournament.find_team_by_id(team_id)
            if not team:
                return f"Team `{team_id}` not found in the tournament {tournament.alias}"

            if team.captain:
                self._remove_discord_team_captain(
                    self.build_identifier(team.captain), tournament.captain_role
                )
            tournament.teams.remove(team)

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return f"Team {team.name} successfully removed."

    @arg_botcmd("alias", type=str, admin_only=True)
    @tournament_admin_only
    def remove_tournament(self, msg, alias):
        """
        [Admin] Associate a Discord role to a tournament.
        E.g. `!remove tournament fortnite`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found."

        with self.mutable("tournaments") as tournaments:
            tournaments.pop(alias)
            return f"Tournament successfully removed."

    @arg_botcmd("status", type=str)
    @arg_botcmd("match_name", type=str)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def set_match_status(self, msg, alias: str, match_name: str, status: str):
        """
        [Admin] Force the match status state.
        E.g. !set match status fortnite match_1 completed
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            match = tournament.find_match_by_name(match_name)
            if not match:
                return "Match not found"

            if not hasattr(MatchStatus, status.upper()):
                return (
                    f"Match status `{status}` doesn't exists. "
                    f"Choices are: {[s.name for s in MatchStatus]}"
                )

            match.status = MatchStatus[status.upper()]

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return f"Match `{match_name}` status set to `{status.upper()}`."

    @arg_botcmd("team_id", type=int)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def reset_team(self, msg: Message, alias: str, team_id: int):
        """
        [Admin] Reset a team information and linked captain.
        E.g. `!reset team fortnite 123456789`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            team = tournament.find_team_by_id(team_id)
            if not team:
                return (
                    f"Team `{team_id}` not found in the tournament {tournament.alias}"
                    f". Try to refresh the tournament instead."
                )

            participant = self.toornament_api_client.get_participant(
                tournament.id, team.id
            )
            if not participant:
                return "Could not retrieve participant's info"

            if team.captain:
                self._remove_discord_team_captain(
                    self.build_identifier(team.captain), tournament.captain_role
                )
            team.captain = None
            team.lineup = [Player.from_dict(pl) for pl in participant["lineup"]]
            team.custom_fields = participant["custom_fields"]
            team.checked_in = participant["checked_in"]

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            return f"Team {team.name} successfully updated."

    @arg_botcmd("match_name", type=str)
    @arg_botcmd("alias", type=str)
    @private_message_only
    def show_match(self, msg, alias: str, match_name: str):
        """
        Show a tournament's match.
        E.g. `!show match fortnite match1`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        tournament = Tournament.from_dict(self["tournaments"][alias])
        match = tournament.find_match_by_name(match_name)
        if not match:
            return f"Match `{match_name}` not found in tournament `{tournament.alias}`"

        self._show_match(msg, tournament, match)

    @arg_botcmd("alias", type=str)
    @tournament_channel_only
    def show_matches(self, msg, alias):
        """
        Show the matches of a tournament.
        E.g. `!show matches fortnite`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        fields = []
        tournament = Tournament.from_dict(self["tournaments"][alias])
        team = tournament.find_team_by_captain(msg.frm.fullname)
        for match in tournament.matches:
            fields.append(
                (
                    str(match.name),
                    (
                        str(match) + "*You have joined this match*"
                        if bool(team and team.id in match.teams_joined)
                        else str(match)
                    ),
                )
            )

        self.send_card(
            title=tournament.alias, fields=fields, in_reply_to=msg, color="grey"
        )

    @arg_botcmd("match_name", type=str)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def show_match_scores(self, msg, alias: str, match_name: str):
        """
        [Admin] Show a tournament match score submissions.
        E.g. `!show match scores fortnite match_1`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        tournament = Tournament.from_dict(self["tournaments"][alias])
        match = tournament.find_match_by_name(match_name)
        if not match:
            return f"Match `{match_name}` not found."

        match_scores = tournament.get_match_scores(match_name)
        if not match_scores:
            return "No score submissions found for this match."

        match_scores = sorted(match_scores, key=lambda k: getattr(k, "position"))
        match_scores_chunk = chunks(match_scores, 25)

        for i, chunk in enumerate(match_scores_chunk):
            self.send_card(
                title=f"{match.name} @ {tournament.alias} Score Submissions "
                f"({i + 1}/{len(match_scores_chunk)})",
                fields=((str(score.team_name), str(score)) for score in chunk),
                in_reply_to=msg,
                color="grey",
            )

    @botcmd
    @private_message_only
    def show_scores(self, msg, *args):
        """
        [Linked] Show your team match score submissions history.
        E.g. `!show scores`
        """
        team, tournament = self._find_captain_team(msg.frm.fullname, self["tournaments"])
        if not team:
            return "You are not linked to a team."

        self.send_card(
            title=f"{team.name} @ {tournament.alias} Score Submissions",
            fields=(
                (str(score.match_name), str(score)) for score in team.score_submissions
            ),
            in_reply_to=msg,
            color="grey",
        )

    @botcmd
    @private_message_only
    def show_status(self, msg, args):
        """ Show your currently linked team and joined matched. """
        team, tournament = self._find_captain_team(msg.frm.fullname, self["tournaments"])
        if not team:
            return "You are not the captain of a team."

        self.send_card(
            title=f"{team.name} Team @ {tournament.info.name}",
            summary=f"To unregister, type:\n!unlink {team.name}",
            to=self.build_identifier(msg.frm.fullname),
            **team.show_card(),
            color="green",
        )

        joined_matches = []
        for match in tournament.matches:
            if team.id in match.teams_joined:
                joined_matches.append(match)

        if joined_matches:
            self.send_card(
                title=f"{team.name} Matches @ {tournament.info.name}",
                to=self.build_identifier(msg.frm.fullname),
                fields=(
                    (
                        match.name,
                        (
                            f"**Status:** {match.status.name}\n"
                            f"**Password:** {match.password}\n"
                            f"**Score Submission:** "
                            f"{str(team.find_submission_by_match(match.name))}"
                        ),
                    )
                    for match in joined_matches
                ),
            )

    @arg_botcmd("team_name", type=str, nargs="+")
    @arg_botcmd("alias", type=str)
    @tournament_channel_only
    def show_team(self, msg: Message, alias: str, team_name: List[str]):
        """
        Show a team information.
        E.g. `!show team fortnite Team Liquid`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        team_name = " ".join(team_name)

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            team = tournament.find_team_by_name(team_name)
            if not team:
                return (
                    f"Team `{team_name}` not found in the tournament `{tournament.alias}`"
                )

            self.send_card(
                in_reply_to=msg,
                title=f"{team.name} @ {tournament.info.name}",
                **team.show_card(),
                color="grey",
            )

    @arg_botcmd("team_id", type=int)
    @arg_botcmd("alias", type=str)
    @tournament_channel_only
    def show_team_by_id(self, msg: Message, alias: str, team_id: int):
        """
        Show a team information.
        E.g. `!show team by id fortnite 123456789`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        tournament = Tournament.from_dict(self["tournaments"][alias])
        team = tournament.find_team_by_id(team_id)
        if not team:
            return f"Team `{team.name}` not found in the tournament `{tournament.alias}`"

        self.send_card(
            in_reply_to=msg,
            title=f"{team.name} @ {tournament.info.name}",
            **team.show_card(),
            color="grey",
        )

    @arg_botcmd("alias", type=str)
    @private_message_only
    def show_teams(self, msg: Message, alias):
        """
        Show teams linked on Discord.
        E.g. `!show teams fortnite`
        """
        if alias not in self["tournaments"]:
            return "Tournament doesn't exists"

        tournament = Tournament.from_dict(self["tournaments"][alias])
        participants = sorted(tournament.teams, key=lambda k: getattr(k, "name"))
        participants = [p for p in participants if p.captain is not None]
        if len(participants) == 0:
            return "No team registered for this tournament"

        count = 1
        participants_chunks = chunks(participants, 100)
        for i, chunk in enumerate(participants_chunks):
            team_names = ""
            for team in chunk:
                team_names += f"{count}. {team.name}\n"
                count += 1

            self.send_card(
                title=f"{tournament.alias} Registered Participants"
                f"({i + 1}/{len(participants_chunks)})",
                body=(
                    f"Number of teams: "
                    f"{len(tournament.teams)} \n"
                    f"Number of registrations: "
                    f"{tournament.count_linked_teams()}\n\n"
                    f"{team_names}"
                ),
                color="grey",
                in_reply_to=msg,
            )

    @arg_botcmd("alias", type=str)
    @private_message_only
    def show_teams_missing(self, msg: Message, alias):
        """
        Show teams not linked on Discord.
        E.g. `!show teams missing fortnite`
        """
        if alias not in self["tournaments"]:
            return "Tournament doesn't exists"

        tournament = Tournament.from_dict(self["tournaments"][alias])
        participants = sorted(tournament.teams, key=lambda k: getattr(k, "name"))
        participants = [p for p in participants if p.captain is None]
        if len(participants) == 0:
            return "Every team are registered for this tournament"

        missing_participants_count = (
            len(tournament.teams) - tournament.count_linked_teams()
        )
        count = 1
        participants_chunks = chunks(participants, 100)
        for i, chunk in enumerate(participants_chunks):
            team_names = ""
            for team in chunk:
                team_names += f"{count}. {team.name}\n"
                count += 1

            self.send_card(
                title=f"{tournament.alias} Missing Registrations "
                f"({i + 1}/{len(participants_chunks)})",
                body=(
                    f"Number of teams: "
                    f"{len(tournament.teams)} \n"
                    f"Number of missing registrations: "
                    f"{missing_participants_count}\n\n"
                    f"{team_names}"
                ),
                color="grey",
                in_reply_to=msg,
            )

    @arg_botcmd("alias", type=str)
    def show_tournament(self, msg, alias):
        """
        Show a tournament.
        E.g. `!show tournament fortnite`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found."
        tournament = Tournament.from_dict(self["tournaments"][alias])
        self._show_tournament(msg, tournament)

    @botcmd
    def show_tournaments(self, msg, args):
        """ Show available tournaments. E.g. `!show tournaments` """
        if self["tournaments"]:
            for tournament in self["tournaments"].values():
                tournament = Tournament.from_dict(tournament)
                self._show_tournament(msg, tournament)
        else:
            return "No tournaments to show."

    @arg_botcmd("match_name", type=str)
    @arg_botcmd("alias", type=str)
    @tournament_admin_only
    def start_match(self, msg, alias: str, match_name: str):
        """
        [Admin] Start a tournament match.
        This will send a notification in the tournament's channels (if exists) and to the
        linked captains of this tournament that the match is going to start in 30 seconds.
        E.g. `!start match fortnite match_1`
        """
        if alias not in self["tournaments"]:
            return "Tournament not found"

        with self.mutable("tournaments") as tournaments:
            tournament = Tournament.from_dict(tournaments[alias])
            match = tournament.find_match_by_name(match_name)
            if not match:
                return "Match not found"
            if match.status != MatchStatus.PENDING:
                return f"Can't start match with status `{match.status.name}`"

            for channel in tournament.channels:
                room = self.query_room(channel)
                self.send(room, f"The match `{match_name}` will start in ~30 seconds!")

            for team_id in match.teams_joined:
                team = tournament.find_team_by_id(team_id)
                captain_user = self.build_identifier(team.captain)
                self.send(
                    captain_user,
                    f"The match `{match_name}` for the team `{team.name}` "
                    f"will start in ~30 seconds!",
                )

            match.status = MatchStatus.ONGOING

            # Save tournament changes to db
            tournaments.update({alias: tournament.to_dict()})
            self.send(msg.frm, f"Match `{match_name}` status set to ONGOING.")

    @arg_botcmd("team_name", type=str, nargs="+")
    @tournament_channel_only
    def unlink(self, msg: Message, team_name: List[str]):
        """
        [Linked] Unlink your current team with your Discord account.
        E.g. `!unlink Team SoloMid`
        """

        team_name = " ".join(team_name)
        with self.mutable("tournaments") as tournaments:
            team, tournament = self._find_captain_team(msg.frm.fullname, tournaments)
            if not team:
                return "You are not the captain of a team."

            if team.name != team_name:
                return (
                    f"Your linked team name `{team.name}` is different from "
                    f"your entry `{team_name}`. To confirm your unregistration, please "
                    f"type the right team name."
                )

            team.captain = None

            # Save tournament changes to db
            tournaments.update({tournament.alias: tournament.to_dict()})
            self._remove_discord_team_captain(msg.frm, tournament.captain_role)
            return f"You are no longer the captain of the team `{team_name}`."

    @staticmethod
    def _add_discord_team_captain(
        user: DiscordPerson, team_name: str, captain_role: Optional[str]
    ):
        """
        Update Discord user nickname and add role if tournament captain_role is set
        """
        # magic number 32, discord max username length, shhht
        max_length = 32 - (len(user.nick) + 4)
        discord_team_name = team_name[:max_length] + (team_name[max_length:] and "..")
        discord_captain_name = f"{user.nick}[{discord_team_name}]"

        # Update username nickname
        user.edit_nickname(discord_captain_name)

        if captain_role:
            if not user.has_guild_role(captain_role):
                sleep(1)
                user.add_role(captain_role)

    @staticmethod
    def _find_captain_team(
        username: str, tournaments: dict
    ) -> Tuple[Optional[Team], Optional[Tournament]]:
        for t in tournaments.values():
            tournament = Tournament.from_dict(t)
            team = tournament.find_team_by_captain(username)
            if team:
                return team, tournament
        return None, None

    @staticmethod
    def _remove_discord_team_captain(user: DiscordPerson, captain_role: Optional[str]):
        """
        Reset Discord user nickname and remove role if tournament captain_role is set
        """
        user.edit_nickname(user.username)

        if captain_role:
            if user.has_guild_role(captain_role):
                sleep(1)
                user.remove_role(captain_role)

    def _show_match(self, msg, tournament: Tournament, match: Match):
        team = tournament.find_team_by_captain(msg.frm.fullname)
        fields = [
            ("Status", f"{match.status.name}\n"),
            (
                "Teams Joined",
                f"{len(match.teams_joined)}/" f"{len(match.teams_registered)}\n",
            ),
            ("Created by", f"{match.created_by}\n"),
            ("Match ID", f"{match.id}\n"),
            ("Group", f"{match.group_name}\n"),
        ]

        has_joined_the_match = bool(team and team.id in match.teams_joined)
        if has_joined_the_match:
            fields.append(("Password", f"{match.password}\n"))

        self.send_card(
            title=f"{match.name} @ {tournament.alias}",
            fields=fields,
            to=self.build_identifier(msg.frm.fullname),
            color="green" if has_joined_the_match else "grey",
        )

    def _show_tournament(self, msg, tournament: Tournament):
        team_status_text = "**You are not the captain of a team in this tournament*"
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
            body=f"{tournament.url}\n\n{team_status_text}",
            summary=f"Tournament Administrators:\t{admins}",
            color="green" if team else "grey",
            in_reply_to=msg,
            **tournament.show_card(),
        )

    def _is_tournament_admin(self, user: DiscordPerson) -> bool:
        admin_roles = list(
            itertools.chain(
                *[t["administrator_roles"] for t in self["tournaments"].values()]
            )
        )
        if user.fullname in self.bot_config.BOT_ADMINS or any(
            user.has_guild_role(r) for r in admin_roles
        ):
            return True
        return False
