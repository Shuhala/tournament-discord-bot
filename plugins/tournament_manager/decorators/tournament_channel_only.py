from functools import wraps


def tournament_channel_only(func):
    """ Allow a command to be used in private message only """

    @wraps(func)
    def wrap(*args, **kwargs):
        def sanitize_channel(name):
            return name.replace("<", "").replace(">", "")

        plugin, msg, *_ = args
        room = sanitize_channel(str(msg.frm.room))
        tournament_channels = plugin["tournaments"][kwargs["alias"]]["channels"]
        # no tournament channel set
        if not tournament_channels:
            return func(*args, **kwargs)
        # tournament channel set
        for channel in tournament_channels:
            if sanitize_channel(channel) == room:
                return func(*args, **kwargs)

        plugin.send(
            msg.frm,
            "Please use this command in the tournament assigned bot channels: "
            + " ".join(tournament_channels),
        )

    return wrap
