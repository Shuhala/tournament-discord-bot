import logging
from configparser import ConfigParser

config = ConfigParser()
config.read("config.ini")

BACKEND = config["DEFAULT"]["BACKEND"]

BOT_ADMINS = tuple(config["DEFAULT"]["BOT_ADMINS"].split(","))
BOT_ALT_PREFIXES = tuple(config["DEFAULT"]["BOT_ALT_PREFIXES"].split(","))

BOT_DATA_DIR = r"./data"
BOT_EXTRA_BACKEND_DIR = "./backends"
BOT_EXTRA_PLUGIN_DIR = r"./plugins"

BOT_LOG_FILE = r"./logs/errbot.log"
BOT_LOG_LEVEL = logging.DEBUG

SUPPRESS_CMD_NOT_FOUND = True

BOT_ASYNC = True
BOT_ASYNC_POOLSIZE = 10

BOT_IDENTITY = {"token": config["DEFAULT"]["BOT_IDENTITY"]}

CORE_PLUGINS = ("TournamentManager", "Health", "Backup")
