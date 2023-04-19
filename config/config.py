# fmt: off

import os
import json

from config.utils import get_env_var, alchemize_url


DEFAULTS = {
    "BOT_TOKEN": "MTA5NTQxNjk3NTAyODY1MDA0Ng.G9mzA1.zrUpqTdFbN8Tn9LsoBeMoT-CLrbsGQ4loi1-RI",
    "SPOTIFY_ID": "cb9c5371a4b247d88d7fe63b9379d717",
    "SPOTIFY_SECRET": "91694da0d6b94437873156fc934a3ca3",

    "BOT_PREFIX": "p",  # set to empty string to disable
    "ENABLE_SLASH_COMMANDS": False,

    "VC_TIMEOUT": 600,  # seconds
    "VC_TIMOUT_DEFAULT": True,  # default template setting for VC timeout true= yes, timeout false= no timeout

    "MAX_SONG_PRELOAD": 5,  # maximum of 25
    "MAX_HISTORY_LENGTH": 10,
    "MAX_TRACKNAME_HISTORY_LENGTH": 15,

    # if database is not one of sqlite, postgres or MySQL
    # you need to provide the url in SQL Alchemy-supported format.
    # Must be async-compatible
    # CHANGE ONLY IF YOU KNOW WHAT YOU'RE DOING
    "DATABASE_URL": os.getenv("HEROKU_DB") or "sqlite:///settings.db",
}


if os.path.isfile("config.json"):
    with open("config.json") as f:
        DEFAULTS.update(json.load(f))
elif not os.getenv("SENKU_INSTALLING"):
    with open("config.json", "w") as f:
        json.dump(DEFAULTS, f, indent=2)


for key, default in DEFAULTS.items():
    globals()[key] = get_env_var(key, default)


MENTION_AS_PREFIX = True

ENABLE_BUTTON_PLUGIN = True

EMBED_COLOR = 0x4dd4d0  # replace after'0x' with desired hex code ex. '#ff0188' >> '0xff0188'

SUPPORTED_EXTENSIONS = (".webm", ".mp4", ".mp3", ".avi", ".wav", ".m4v", ".ogg", ".mov")


COOKIE_PATH = "/config/cookies/cookies.txt"

GLOBAL_DISABLE_AUTOJOIN_VC = False

ALLOW_VC_TIMEOUT_EDIT = True  # allow or disallow editing the vc_timeout guild setting


actual_prefix = (  # for internal use
    BOT_PREFIX
    if BOT_PREFIX
    else ("/" if ENABLE_SLASH_COMMANDS else "@bot ")
)

# set db url during install even if it's overriden by env
if os.getenv("DANDELION_INSTALLING") and not DATABASE_URL:
    DATABASE_URL = DEFAULTS["DATABASE_URL"]
DATABASE = alchemize_url(DATABASE_URL)
DATABASE_LIBRARY = DATABASE.partition("+")[2].partition(":")[0]


STARTUP_MESSAGE = "Encendiendo Bot..."
STARTUP_COMPLETE_MESSAGE = "Bot Encendido"

NO_GUILD_MESSAGE = "Error: Please join a voice channel or enter the command in guild chat"
USER_NOT_IN_VC_MESSAGE = "Error: Por favor entra a un canal de voz activo para poder usar los comandos"
WRONG_CHANNEL_MESSAGE = "Error: Please use configured command channel"
NOT_CONNECTED_MESSAGE = "Error: El Bot no está conectado a ningún canal de voz"
ALREADY_CONNECTED_MESSAGE = "Error: Ya me encuentro conectado a otro canal de voz"
NOT_A_DJ = "No eres un DJ"
USER_MISSING_PERMISSIONS = "No tienes permiso para esto."
CHANNEL_NOT_FOUND_MESSAGE = "Error: No se pudo encontrar el canal"
DEFAULT_CHANNEL_JOIN_FAILED = "Error: Could not join the default voice channel"
INVALID_INVITE_MESSAGE = "Error: Invalid invitation link"

ADD_MESSAGE = "To add this bot to your own Server, click [{https://discord.com/api/oauth2/authorize?client_id=1095416975028650046&permissions=3147776&scope=bot}]"  # brackets will be the link text

INFO_HISTORY_TITLE = "Canciones Reproducidas:"

SONGINFO_UPLOADER = "Uploader: "
SONGINFO_DURATION = "Duración: "
SONGINFO_SECONDS = "s"
SONGINFO_LIKES = "Likes: "
SONGINFO_DISLIKES = "Dislikes: "
SONGINFO_NOW_PLAYING = "Reproduciendo Ahora"
SONGINFO_QUEUE_ADDED = "Añadido a la cola"
SONGINFO_SONGINFO = "Información de la canción"
SONGINFO_ERROR = "Error: Sitio inhabilitado o contenido con control de edad. Para habilitar el contenido con restricción de edad visite documentation/wiki."
SONGINFO_PLAYLIST_QUEUED = "Playlist añadido a la cola :page_with_curl:"
SONGINFO_UNKNOWN_DURATION = "Desconocido"
QUEUE_EMPTY = "La cola está vacia :x:"

HELP_ADDBOT_SHORT = "Añade el bot a otro servidor"
HELP_ADDBOT_LONG = "Gives you the link for adding this bot to another server of yours."
HELP_CONNECT_SHORT = "Conecta el bot al canal de voz"
HELP_CONNECT_LONG = "Conecta el bot al canal de voz en el que te encuentras"
HELP_DISCONNECT_SHORT = "Desconecta el bot del canal de voz"
HELP_DISCONNECT_LONG = "Desconecta el bot del canal de voz y desconecta el audio"

HELP_SETTINGS_SHORT = "Ver y asignar opciones del bot"
HELP_SETTINGS_LONG = "Ver y asignar opciones del bot en el servidor. Usa: {}settings setting_name value".format(actual_prefix)

HELP_HISTORY_SHORT = "Muestra el historial de las canciones"
HELP_HISTORY_LONG = "Muestra las " + str(MAX_TRACKNAME_HISTORY_LENGTH) + " ultimas canciones reproducidas."
HELP_PAUSE_SHORT = "Pausar música"
HELP_PAUSE_LONG = "Pausa el AudioPlayer. Usalo de nuevo para resumir."
HELP_VOL_SHORT = "Cambiar el porcentaje de volumen"
HELP_VOL_LONG = "Cambia el volumen del AudioPlayer. Especifica cuando porcentaje debería ser asignado."
HELP_PREV_SHORT = "Go back one Song"
HELP_PREV_LONG = "Plays the previous song again."
HELP_SKIP_SHORT = "Skip a song"
HELP_SKIP_LONG = "Skips the currently playing song and goes to the next item in the queue."
HELP_SONGINFO_SHORT = "Info about current Song"
HELP_SONGINFO_LONG = "Shows details about the song currently being played and posts a link to the song."
HELP_STOP_SHORT = "Stop Music"
HELP_STOP_LONG = "Stops the AudioPlayer and clears the songqueue"
HELP_MOVE_LONG = f"{actual_prefix}move [position] [new position]"
HELP_MOVE_SHORT = "Moves a track in the queue"
HELP_YT_SHORT = "Play a supported link or search on youtube"
HELP_YT_LONG = f"{actual_prefix}p [link/video title/keywords/playlist/soundcloud link/spotify link/bandcamp link/twitter link]"
HELP_PING_SHORT = "Pong"
HELP_PING_LONG = "Test bot response status"
HELP_CLEAR_SHORT = "Clear the queue."
HELP_CLEAR_LONG = "Clears the queue and skips the current song."
HELP_LOOP_SHORT = "Loops the currently playing song or queue."
HELP_LOOP_LONG = "Loops the currently playing song or queue. Modes are all/single/off."
HELP_QUEUE_SHORT = "Shows the songs in queue."
HELP_QUEUE_LONG = "Shows the number of songs in queue, up to 10."
HELP_SHUFFLE_SHORT = "Shuffle the queue"
HELP_SHUFFLE_LONG = "Randomly sort the songs in the current queue"
HELP_RESET_SHORT = "Disconnect and reconnect"
HELP_RESET_LONG = "Stop player, disconnect and reconnect to the channel you are in"
HELP_REMOVE_SHORT = "Remove a song"
HELP_REMOVE_LONG = "Allows to remove a song from the queue by typing it's position (defaults to the last song)."

ABSOLUTE_PATH = ""  # do not modify
