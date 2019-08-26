from functools import wraps


def private_message_only(func):
    """ Allow a command to be used in private message only """

    @wraps(func)
    def wrap(*args, **kwargs):
        plugin, msg, *_ = args
        if msg.is_direct:
            return func(*args, **kwargs)
        plugin.send(msg.frm, "Please use this command in private message.")

    return wrap
