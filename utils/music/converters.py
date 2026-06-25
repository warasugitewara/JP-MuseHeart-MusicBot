# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import json
import re
import traceback
from typing import Union, TYPE_CHECKING

import disnake

if TYPE_CHECKING:
    pass

URL_REG = re.compile('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|%[0-9a-fA-F][0-9a-fA-F])+')
YOUTUBE_VIDEO_REG = re.compile(r"(https?://)?(www\.|music\.)?youtube\.(com|nl)/watch\?v=([-\w]+)")

replaces = [
    ('&quot;', '"'),
    ('&amp;', '&'),
    ('(', '\u0028'),
    (')', '\u0029'),
    ('[', '【'),
    (']', '】'),
    ("  ", " "),
    ("*", '"'),
    ("_", ' '),
    ("{", "\u0028"),
    ("}", "\u0029"),
    ("`", "'")
]


async def google_search(bot, query: str, *, max_entries: int = 20) -> list:

    try:
        async with bot.session.get(
                "https://suggestqueries.google.com/complete/search",
                headers={'User-Agent': bot.pool.current_useragent} if bot.pool.current_useragent else None,
                params={
                    'client': 'youtube',
                    'q': query,
                    'ds': 'yt',
                    'hl': 'en'
                }
        ) as r:

            text = await r.text()
            json_text = text[text.find("(") + 1:text.rfind(")")]
            return [result[0] for result in json.loads(json_text)[1][:max_entries]]
    except:
        traceback.print_exc()
        return []


def get_button_style(enabled: bool, red=True):
    if enabled:
        if red:
            return disnake.ButtonStyle.red
        return disnake.ButtonStyle.green
    return disnake.ButtonStyle.grey


def fix_characters(text: str, limit: int = 0):
    for r in replaces:
        old, new = r
        text = text.replace(old, new)

    if limit:
        text = f"{text[:limit]}..." if len(text) > limit else text

    return text


def time_format(milliseconds: Union[int, float], use_names: bool = False) -> str:
    minutes, seconds = divmod(int(milliseconds / 1000), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    if use_names:

        times = []

        for time_, name in (
                (days, "dia"),
                (hours, "hora"),
                (minutes, "minuto"),
                (seconds, "segundo")
        ):
            if not time_:
                continue

            times.append(f"{time_} {name}" + ("s" if time_ > 1 else ""))

        try:
            last_time = times.pop()
        except IndexError:
            last_time = None
            times = ["1 segundo"]

        strings = ", ".join(t for t in times)

        if last_time:
            strings += f" e {last_time}" if strings else last_time

    else:

        strings = f"{minutes:02d}:{seconds:02d}"

        if hours:
            strings = f"{hours}:{strings}"

        if days:
            strings = (f"{days} dias" if days > 1 else f"{days} dia") + (f", {strings}" if strings != "00:00" else "")

    return strings


time_names = ["seconds", "minutes", "hours"]


def string_to_seconds(time):
    try:

        times = reversed([i for i in time.replace(" ", ":").split(':') if i.isdigit()])
        time_dict = {}

        for n, t in enumerate(times):
            time_dict[time_names[n]] = int(t)

        return datetime.timedelta(**time_dict).total_seconds()

    except:
        return


def percentage(part, whole):
    return int((part * whole) / 100.0)

sources = {
    "deezer": "https://iili.io/d1Kjip1.png",
    "soundcloud": "https://iili.io/d1KjPkP.md.png",
    "spotify": "https://iili.io/d1KVvlS.png",
    "youtube": "https://iili.io/d1KjLTF.md.png",
    "applemusic": "https://iili.io/d1Kj6YB.md.png",
    "twitch": "https://cdn3.iconfinder.com/data/icons/popular-services-brands-vol-2/512/twitch-512.png",
    "jiosaavn": "https://iili.io/d1KjUEx.png",
    "tidal": "https://iili.io/d1KjgrQ.png",
    "youtubemusic": "https://iili.io/d1Kj42V.png",
    "last.fm": "https://cdn.discordapp.com/emojis/1278883704097341541.png",
}

def music_source_image(sourcename):
    return sources.get(
        sourcename,
        "https://cdn.discordapp.com/attachments/480195401543188483/895862881105616947/music_equalizer.gif"
    )


perms_translations = {
    "add_reactions": "リアクションの追加",
    "administrator": "管理者",
    "attach_files": "ファイルの添付",
    "ban_members": "メンバーをBAN",
    "change_nickname": "ニックネームの変更",
    "connect": "ボイスチャンネルへの接続",
    "create_instant_invite": "招待リンクの作成",
    "create_private_threads": "プライベートスレッドの作成",
    "create_public_threads": "公開スレッドの作成",
    "deafen_members": "メンバーのスピーカーミュート",
    "embed_links": "埋め込みリンク",
    "kick_members": "メンバーをキック",
    "manage_channels": "チャンネルの管理",
    "manage_emojis_and_stickers": "絵文字とスタンプの管理",
    "manage_events": "イベントの管理",
    "manage_guild": "サーバーの管理",
    "manage_messages": "メッセージの管理",
    "manage_nicknames": "ニックネームの管理",
    "manage_roles": "ロールの管理",
    "manage_threads": "スレッドの管理",
    "manage_webhooks": "ウェブフックの管理",
    "mention_everyone": "@everyone と @here のメンション",
    "moderate_members": "メンバーのタイムアウト",
    "move_members": "メンバーの移動",
    "mute_members": "メンバーのミュート",
    "priority_speaker": "優先スピーカー",
    "read_message_history": "メッセージ履歴を読む",
    "read_messages": "メッセージを読む",
    "request_to_speak": "発言をリクエスト",
    "send_messages": "メッセージの送信",
    "send_messages_in_threads": "スレッドでメッセージを送信",
    "send_tts_messages": "テキスト読み上げメッセージの送信",
    "speak": "ボイスチャンネルでの発言",
    "stream": "配信",
    "use_application_commands": "アプリ/ボットコマンドの使用",
    "use_embedded_activities": "アクティビティの使用",
    "use_external_emojis": "外部の絵文字の使用",
    "use_external_stickers": "外部のスタンプの使用",
    "use_voice_activation": "音声検出の使用",
    "view_audit_log": "監査ログの表示",
    "view_channel": "チャンネルを見る",
    "view_guild_insights": "サーバーインサイトの表示"
}
