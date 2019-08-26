from functools import wraps


def tournament_admin_only(func):
    """ Allow a command to be used by a tournament admin only """

    @wraps(func)
    def wrap(*args, **kwargs):
        plugin, msg, *_ = args

        # is superuser
        if msg.frm.fullname in plugin.bot_config.BOT_ADMINS:
            return func(*args, **kwargs)

        # is tournament admin
        for tournament in plugin["tournaments"].values():
            if any(msg.frm.has_guild_role(r) for r in tournament["administrator_roles"]):
                return func(*args, **kwargs)

        plugin.send(msg.frm, "You are not allowed to perform this action")

    return wrap
