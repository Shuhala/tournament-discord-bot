from functools import wraps


def tournament_channel_only(func):
    """
    Allow a command to be used in the bot tournament channels if set or in private message
    Can retrieve the tournament channels when the command provides a tournament `alias`,
    or if the command is sent by a Discord user linked to a tournament.
    Otherwise the command is authorized by default (tournament_channels is None)
    """

    @wraps(func)
    def wrap(*args, **kwargs):
        def sanitize_channel(name):
            return name.replace("<", "").replace(">", "")

        plugin, msg, *_ = args
        tournament_channels = None
        if hasattr(kwargs, "alias"):
            tournament_channels = plugin["tournaments"][kwargs["alias"]]["channels"]
        else:
            _, tournament = plugin._find_captain_team(
                msg.frm.fullname, plugin["tournaments"]
            )
            if tournament:
                tournament_channels = tournament.channels

        if msg.is_direct:
            return func(*args, **kwargs)

        room = sanitize_channel(str(msg.frm.room))
        # no tournament channel set
        if not tournament_channels:
            return func(*args, **kwargs)
        # tournament channel set
        for channel in tournament_channels:
            if sanitize_channel(channel) == room:
                return func(*args, **kwargs)

        plugin.send(
            msg.frm,
            "Please use this command in private or in the tournament "
            "assigned bot channels: " + " ".join(tournament_channels),
        )

    return wrap
