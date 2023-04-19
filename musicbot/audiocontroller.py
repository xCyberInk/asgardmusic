import asyncio
from enum import Enum
from itertools import islice
from inspect import isawaitable
from typing import TYPE_CHECKING, Coroutine, Optional, List, Tuple

import discord
from config import config

from musicbot import linkutils, utils
from musicbot.playlist import Playlist
from musicbot.songinfo import Song
from musicbot.utils import CheckError, compare_components, play_check

# avoiding circular import
if TYPE_CHECKING:
    from musicbot.bot import MusicBot

_not_provided = object()
_search_lock = asyncio.Lock()


class PauseState(Enum):
    NOTHING_TO_PAUSE = "Nothing to pause or resume."
    PAUSED = "Playback Paused :pause_button:"
    RESUMED = "Resumed playback :arrow_forward:"


class LoopState(Enum):
    INVALID = "Invalid loop mode!"
    ENABLED = "Loop enabled :arrows_counterclockwise:"
    DISABLED = "Loop disabled :x:"


class MusicButton(discord.ui.Button):
    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self._callback = callback

    async def callback(self, inter):
        ctx = await inter.client.get_application_context(inter)
        try:
            await play_check(ctx)
        except CheckError as e:
            await ctx.send(e, ephemeral=True)
            return
        await inter.response.defer()
        res = self._callback(ctx)
        if isawaitable(res):
            await res


LOOP_MODES = ("all", "single", "off")


class AudioController(object):
    """Controls the playback of audio and the sequential playing of the songs.

    Attributes:
        bot: The instance of the bot that will be playing the music.
        playlist: A Playlist object that stores the history and queue of songs.
        current_song: A Song object that stores details of the current song.
        guild: The guild in which the Audiocontroller operates.
    """

    def __init__(self, bot: "MusicBot", guild: discord.Guild):
        self.bot = bot
        self.playlist = Playlist()
        self.current_song = None
        self._next_song = None
        self.guild = guild

        sett = bot.settings[guild]
        self._volume: int = sett.default_volume

        self.timer = utils.Timer(self.timeout_handler)

        self.command_channel: Optional[discord.abc.Messageable] = None

        self.last_message = None
        self.last_view = None

        # according to Python documentation, we need
        # to keep strong references to all tasks
        self._tasks = set()

        self._preloading = {}
        self.message_lock = asyncio.Lock()

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value: int):
        self._volume = value
        try:
            self.guild.voice_client.source.volume = float(value) / 100.0
        except Exception:
            pass

    def volume_up(self):
        self.volume = min(self.volume + 10, 100)

    def volume_down(self):
        self.volume = max(self.volume - 10, 10)

    async def register_voice_channel(self, channel: discord.VoiceChannel):
        await channel.connect(reconnect=True, timeout=None)

    async def extract_info(self, url: str, options: dict) -> dict:
        downloader = None
        for o, d in _cached_downloaders:
            if o == options:
                downloader = d
                break
        else:
            # we need to copy options because downloader modifies the given dict
            _cached_downloaders.append((options, downloader))
        # if options in _cached_downloaders:
        #     downloader = _cached_downloaders[options]
        # else:
        #     downloader = _cached_downloaders[options] = yt_dlp.YoutubeDL(options)
        async with _search_lock:
            return await self.bot.loop.run_in_executor(
                None, downloader.extract_info, url, False
            )

    async def fetch_song_info(self, song: Song) -> bool:
        try:
            info = await self.extract_info(
                song.info.webpage_url,
                {
                    "format": "bestaudio",
                    "title": True,
                    "cookiefile": config.COOKIE_PATH,
                    "quiet": True,
                },
            )
        except Exception as e:
            if isinstance(e, yt_dlp.DownloadError) and e.exc_info[1].expected:
                return False
            info = await self.extract_info(
                song, {"title": True, "cookiefile": config.COOKIE_PATH, "quiet": True}
            )
        song.update(info)
        return True

    def make_view(self):
        if not self.is_active():
            self.last_view = None
            return None

        view = discord.ui.View(timeout=None)
        is_empty = len(self.playlist) == 0

        prev_button = MusicButton(
            lambda _: self.prev_song(),
            disabled=not self.playlist.has_prev(),
            emoji="⏮️",
        )
        view.add_item(prev_button)

        pause_button = MusicButton(
            lambda _: self.pause(),
            emoji="⏸️" if self.guild.voice_client.is_playing() else "▶️",
        )
        view.add_item(pause_button)

        next_button = MusicButton(
            lambda _: self.next_song(),
            disabled=not self.playlist.has_next(),
            emoji="⏭️",
        )
        view.add_item(next_button)

        loop_button = MusicButton(
            lambda _: self.loop(),
            disabled=is_empty,
            emoji="🔁",
            label="Loop: " + self.playlist.loop,
        )
        view.add_item(loop_button)

        np_button = MusicButton(
            self.current_song_callback,
            row=1,
            disabled=self.current_song is None,
            emoji="💿",
        )
        view.add_item(np_button)

        shuffle_button = MusicButton(
            lambda _: self.playlist.shuffle(),
            row=1,
            disabled=is_empty,
            emoji="🔀",
        )
        view.add_item(shuffle_button)

        queue_button = MusicButton(
            self.queue_callback, row=1, disabled=is_empty, emoji="📜"
        )
        view.add_item(queue_button)

        stop_button = MusicButton(
            lambda _: self.stop_player(),
            row=1,
            emoji="⏹️",
            style=discord.ButtonStyle.red,
        )
        view.add_item(stop_button)

        volume_down_button = MusicButton(
            lambda _: self.volume_down(), row=2, disabled=self.volume == 10, emoji="🔉"
        )
        view.add_item(volume_down_button)

        volume_up_button = MusicButton(
            lambda _: self.volume_up(), row=2, disabled=self.volume == 100, emoji="🔊"
        )
        view.add_item(volume_up_button)

        self.last_view = view

        return view

    async def current_song_callback(self, ctx):
        await ctx.send(
            embed=self.current_song.info.format_output(config.SONGINFO_SONGINFO),
        )

    async def queue_callback(self, ctx):
        await ctx.send(
            embed=self.playlist.queue_embed(),
        )

    async def update_view(self, view=_not_provided):
        msg = self.last_message
        if not msg:
            return
        old_view = self.last_view
        if view is None:
            self.last_message = None
        elif view is _not_provided:
            view = self.make_view()
        if view is old_view:
            return
        elif (
            old_view
            and view
            and compare_components(old_view.to_components(), view.to_components())
        ):
            return
        try:
            await msg.edit(view=view)
        except discord.HTTPException as e:
            if e.code == 50027:  # Invalid Webhook Token
                try:
                    self.last_message = await msg.channel.fetch_message(msg.id)
                    await self.update_view(view)
                except discord.NotFound:
                    self.last_message = None
            else:
                print("Failed to update view:", e)

    def is_active(self) -> bool:
        client = self.guild.voice_client
        return client is not None and (client.is_playing() or client.is_paused())

    def track_history(self):
        history_string = config.INFO_HISTORY_TITLE
        for trackname in self.playlist.trackname_history:
            history_string += "\n" + trackname
        return history_string

    def pause(self):
        client = self.guild.voice_client
        if client:
            if client.is_playing():
                client.pause()
                return PauseState.PAUSED
            elif client.is_paused():
                client.resume()
                return PauseState.RESUMED
        return PauseState.NOTHING_TO_PAUSE

    def loop(self, mode=None):
        if mode is None:
            if self.playlist.loop == "off":
                mode = "all"
            else:
                mode = "off"

        if mode not in LOOP_MODES:
            return LoopState.INVALID

        self.playlist.loop = mode

        if mode == "off":
            return LoopState.DISABLED
        return LoopState.ENABLED

    def next_song(self, error=None):
        """Invoked after a song is finished. Plays the next song if there is one."""

        if self.is_active():
            self.guild.voice_client.stop()
            return

        if self._next_song:
            next_song = self._next_song
            self._next_song = None
        else:
            next_song = self.playlist.next()

        self.current_song = None

        if next_song is None:
            return

        coro = self.play_song(next_song)
        self.add_task(coro)

    async def play_song(self, song: Song):
        """Plays a song object"""

        if self.playlist.loop == "off":  # let timer run thouh if looping
            self.timer.cancel()
            self.timer = utils.Timer(self.timeout_handler)

        if not await self.preload(song):
            self.next_song()
            return

        if song.base_url is None:
            print("Something is wrong. Refusing to play a song without base_url.")
            self.next_song()
            return

        self.playlist.add_name(song.info.title)
        self.current_song = song

        self.guild.voice_client.play(
            discord.FFmpegPCMAudio(
                song.base_url,
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            ),
            after=self.next_song,
        )

        self.guild.voice_client.source = discord.PCMVolumeTransformer(
            self.guild.voice_client.source
        )
        self.guild.voice_client.source.volume = float(self.volume) / 100.0

        if self.bot.settings[self.guild].announce_songs and self.command_channel:
            await self.command_channel.send(
                embed=song.info.format_output(config.SONGINFO_NOW_PLAYING)
            )

        self.add_task(self.preload_queue())

    async def process_song(self, track: str) -> Optional[Song]:
        """Adds the track to the playlist instance and plays it, if it is the first song"""

        host = linkutils.identify_url(track)
        is_playlist = linkutils.identify_playlist(track)

        if is_playlist != linkutils.Playlist_Types.Unknown:

            await self.process_playlist(is_playlist, track)

            if self.current_song is None:
                await self.play_song(self.playlist.playque[0])
                print("Playing {}".format(track))

            song = Song(linkutils.Origins.Playlist, linkutils.Sites.Unknown)
            return song


        if host == linkutils.Sites.Unknown:
            title = await linkutils.convert_spotify(track)

        elif host == linkutils.Sites.Spotify:
            title = await linkutils.convert_spotify(track)

        song = Song(linkutils.Origins.Default, host, webpage_url=track)
        

        self.playlist.add(song)
        if self.current_song is None:
            print("Playing {}".format(track))
            await self.play_song(song)

        return song

    async def process_playlist(self, playlist_type: linkutils.Playlist_Types, url: str):

            
        if playlist_type == linkutils.Playlist_Types.Spotify_Playlist:
            links = await linkutils.get_spotify_playlist(url)
            for link in links:
                song = Song(
                    linkutils.Origins.Playlist,
                    linkutils.Sites.Spotify,
                    webpage_url=link,
                )
                self.playlist.add(song)

        if playlist_type == linkutils.Playlist_Types.BandCamp_Playlist:
            options = {"format": "bestaudio/best", "extract_flat": True, "quiet": True}
            r = await self.extract_info(url, options)

            for entry in r["entries"]:

                link = entry.get("url")

                song = Song(
                    linkutils.Origins.Playlist,
                    linkutils.Sites.Bandcamp,
                    webpage_url=link,
                )

                self.playlist.add(song)

        self.add_task(self.preload_queue())

    def add_task(self, coro: Coroutine):
        task = self.bot.loop.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(lambda t: self._tasks.remove(t))

    async def preload(self, song: Song):

        if song.info.title is not None or song.info.webpage_url is None:
            return True
        future = self._preloading.get(song)
        if future:
            return await future
        self._preloading[song] = asyncio.Future()

        success = True

        if song.host == linkutils.Sites.Spotify:
            title = await linkutils.convert_spotify(song.info.webpage_url)
            

        elif not await self.fetch_song_info(song):
            success = False
        self._preloading.pop(song).set_result(success)
        return success

    async def preload_queue(self):
        rerun_needed = False
        for song in list(islice(self.playlist.playque, 1, config.MAX_SONG_PRELOAD)):
            if not await self.preload(song):
                self.playlist.playque.remove(song)
                rerun_needed = True
        if rerun_needed:
            self.add_task(self.preload_queue())

    
    def stop_player(self):
        """Stops the player and removes all songs from the queue"""
        if not self.is_active():
            return

        self.playlist.loop = "off"
        self.playlist.next()
        self.clear_queue()
        self.guild.voice_client.stop()

    def prev_song(self) -> bool:
        """Loads the last song from the history into the queue and starts it"""

        self.timer.cancel()
        self.timer = utils.Timer(self.timeout_handler)

        prev_song = self.playlist.prev()
        if not prev_song:
            return False

        if not self.is_active():
            self.add_task(self.play_song(prev_song))
        else:
            self._next_song = prev_song
            self.guild.voice_client.stop()
        return True

    async def timeout_handler(self):
        if not self.guild.voice_client:
            return

        if len(self.guild.voice_client.channel.voice_states) == 1:
            await self.udisconnect()
            return

        self.timer = utils.Timer(self.timeout_handler)  # restart timer

        sett = self.bot.settings[self.guild]

        if not sett.vc_timeout or self.guild.voice_client.is_playing():
            return

        await self.udisconnect()

    async def uconnect(self, ctx, move=False):
        author_vc = ctx.author.voice
        bot_vc = self.guild.voice_client

        if not author_vc:
            raise CheckError(config.NO_GUILD_MESSAGE)

        if bot_vc is None:
            await self.register_voice_channel(author_vc.channel)
        elif move and bot_vc.channel != author_vc.channel:
            await bot_vc.move_to(author_vc.channel)
        else:
            raise CheckError(config.ALREADY_CONNECTED_MESSAGE)
        return True

    async def udisconnect(self):
        self.stop_player()
        await self.update_view(None)
        if self.guild.voice_client is None:
            return False
        await self.guild.voice_client.disconnect(force=True)
        return True

    def clear_queue(self):
        self.playlist.playque.clear()
