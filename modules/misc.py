# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import datetime
import json
import os.path
import platform
import traceback
from copy import deepcopy
from itertools import cycle
from os import getpid
from random import shuffle
from typing import TYPE_CHECKING

import aiofiles
import disnake
import humanize
import psutil
from aiohttp import ClientSession
from disnake.ext import commands

from utils.db import DBModel, db_models
from utils.music.checks import check_requester_channel
from utils.music.converters import time_format, URL_REG
from utils.others import select_bot_pool, CustomContext, paginator

if TYPE_CHECKING:
    from utils.client import BotCore


def remove_blank_spaces(d):

    for k, v in list(d.items()):

        new_k = k.strip()
        if new_k != k:
            d[new_k] = d.pop(k)

        if isinstance(v, str):
            new_v = v.strip()
            if new_v != v:
                d[new_k] = new_v
        elif isinstance(v, dict):
            remove_blank_spaces(v)


class Misc(commands.Cog):

    emoji = "🔰"
    name = "その他"
    desc_prefix = f"[{emoji} {name}] | "

    def __init__(self, bot: BotCore):
        self.bot = bot
        self.task = self.bot.loop.create_task(self.presences())
        self.extra_user_bots = []
        self.extra_user_bots_ids = [int(i) for i in bot.config['ADDITIONAL_BOT_IDS'].split() if i.isdigit()]

    def placeholders(self, text: str):

        if not text:
            return ""

        try:
            text = text.replace("{owner}", str(self.bot.owner))
        except AttributeError:
            pass

        if [i for i in ("{players_count}", "{players_user_count}","{players_count_allbotchannels}", "{players_count_allbotservers}") if i in text]:

            channels = set()
            guilds = set()
            users = set()
            player_count = 0

            for bot in self.bot.pool.bots:

                for player in bot.music.players.values():
                    if not player.auto_pause and not player.paused:
                        if bot == self.bot:
                            player_count += 1
                        try:
                            vc = player.guild.me.voice.channel
                        except AttributeError:
                            continue
                        channels.add(vc.id)
                        guilds.add(player.guild.id)
                        for u in vc.members:
                            if u.bot or u.voice.deaf or u.voice.self_deaf:
                                continue
                            users.add(u.id)

                if "{players_count}" in text:
                    if not player_count:
                        return
                    text = text.replace("{players_count}", str(player_count))

            if "{players_count_allbotchannels}" in text:

                if not channels:
                    return

                text = text.replace("{players_count_allbotchannels}", str(len(channels)))

            if "{players_count_allbotservers}" in text:

                if not guilds:
                    return

                text = text.replace("{players_count_allbotservers}", str(len(guilds)))

            if "{players_user_count}" in text:

                if not users:
                    return

                text = text.replace("{players_user_count}", str(len(users)))

        return text \
            .replace("{users}", f'{len([m for m in self.bot.users if not m.bot]):,}'.replace(",", ".")) \
            .replace("{playing}", f'{len(self.bot.music.players):,}'.replace(",", ".")) \
            .replace("{guilds}", f'{len(self.bot.guilds):,}'.replace(",", ".")) \
            .replace("{uptime}", time_format((disnake.utils.utcnow() - self.bot.uptime).total_seconds() * 1000,
                                             use_names=True))

    async def presences(self):

        try:

            activities = []

            for i in self.bot.config["LISTENING_PRESENCES"].split("||"):
                if i:
                    activities.append({"name":i, "type": "listening"})

            for i in self.bot.config["WATCHING_PRESENCES"].split("||"):
                if i:
                    activities.append({"name": i, "type": "watching"})

            for i in self.bot.config["PLAYING_PRESENCES"].split("||"):
                if i:
                    activities.append({"name": i, "type": "playing"})

            for i in self.bot.config["CUSTOM_STATUS_PRESENCES"].split("||"):
                if i:
                    activities.append({"name": i, "type": "custom_status"})

            for i in self.bot.config["STREAMING_PRESENCES"].split("|||"):
                if i:
                    try:
                        name, url = i.split("||")
                        activities.append({"name": name, "url": url.strip(" "), "type": "streaming"})
                    except Exception:
                        traceback.print_exc()

            if not activities:
                return

            shuffle(activities)

            activities = cycle(activities)

            ignore_sleep = False

            await asyncio.sleep(120)

            while True:

                try:
                    if self.bot._presence_loop_started and ignore_sleep is False:
                        await asyncio.sleep(self.bot.config["PRESENCE_INTERVAL"])
                except AttributeError:
                    self.bot._presence_loop_started = True

                await self.bot.wait_until_ready()

                activity_data = next(activities)

                activity_name = self.placeholders(activity_data["name"])

                if not activity_name:
                    await asyncio.sleep(15)
                    ignore_sleep = True
                    continue

                ignore_sleep = False

                if activity_data["type"] == "listening":
                    activity = disnake.Activity(
                        type=disnake.ActivityType.listening,
                        name=activity_name,
                    )

                elif activity_data["type"] == "watching":
                    activity = disnake.Activity(
                        type=disnake.ActivityType.watching,
                        name=activity_name,
                    )

                elif activity_data["type"] == "streaming":
                    activity = disnake.Activity(
                        type=disnake.ActivityType.streaming,
                        name=activity_name,
                        url=activity_data["url"]
                    )

                elif activity_data["type"] == "playing":
                    activity = disnake.Game(name=activity_name)

                else:
                    activity = disnake.Activity(
                        name="customstatus",
                        type=disnake.ActivityType.custom,
                        state=activity_name,
                    )

                await self.bot.change_presence(activity=activity)

                await asyncio.sleep(self.bot.config["PRESENCE_INTERVAL"])

        except Exception:
            traceback.print_exc()


    @commands.Cog.listener("on_guild_join")
    async def guild_add(self, guild: disnake.Guild):

        bots_in_guild = []
        bots_outside_guild = []

        for bot in self.bot.pool.bots:

            if bot == self.bot:
                continue

            if not bot.bot_ready:
                continue

            if bot.user in guild.members:
                bots_in_guild.append(bot)
            else:
                bots_outside_guild.append(bot)

        components = [disnake.ui.Button(custom_id="bot_invite", label="音楽ボットがもっと必要ですか？こちらをクリック。")] if [b for b in self.bot.pool.bots if b.appinfo and b.appinfo.bot_public] else []

        if cmd:=self.bot.get_command("setup"):
            cmd_text = f"ご希望であれば、**/{cmd.name}** コマンドを使用して、コマンドなしで曲をリクエストできる専用チャンネルを作成し、ミュージックプレーヤーを固定チャンネルに設置できます。\n\n"
        else:
            cmd_text = ""

        if self.bot.config["SUPPORT_SERVER"]:
            support_server = f"ご質問がある場合や最新情報をフォローしたい場合は、私の[`サポートサーバー`]({self.bot.config['SUPPORT_SERVER']})に参加できます"
        else:
            support_server = ""

        if self.bot.default_prefix and not self.bot.config["INTERACTION_COMMAND_ONLY"]:
            guild_data = await self.bot.get_global_data(guild.id, db_name=DBModel.guilds)
            prefix = disnake.utils.escape_markdown(guild_data['prefix'], as_needed=True)
        else:
            prefix = ""

        image = "https://cdn.discordapp.com/attachments/554468640942981147/1082887587770937455/rainbow_bar2.gif"

        color = self.bot.get_color()

        send_video = ""

        try:
            channel = guild.system_channel if guild.system_channel.permissions_for(guild.me).send_messages else None
        except AttributeError:
            channel = None

        if not channel:

            if guild.me.guild_permissions.view_audit_log:

                async for entry in guild.audit_logs(action=disnake.AuditLogAction.integration_create, limit=50):

                    if entry.target.application_id == self.bot.user.id:

                        embeds = []

                        embeds.append(
                            disnake.Embed(
                                color=color,
                                description=f"こんにちは！サーバー **{guild.name}** に追加していただき、誠にありがとうございます :)"
                            ).set_image(url=image)
                        )

                        embeds.append(
                            disnake.Embed(
                                color=color,
                                description=f"すべてのコマンドを表示するには、サーバー **{guild.name}** でスラッシュ(**/**)を使用してください"
                            ).set_image(url=image)
                        )

                        if prefix:
                            prefix_msg = f"サーバー **{guild.name}** での私のプレフィックスは: **{prefix}**"
                        else:
                            prefix = self.bot.default_prefix
                            prefix_msg = f"私のデフォルトプレフィックスは **{prefix}**"

                        embeds.append(
                            disnake.Embed(
                                color=color,
                                description=f"プレフィックスによるテキストコマンドもあります。{prefix_msg}（私へのメンションもプレフィックスとして機能します）。"
                                            f"すべてのテキストコマンドを表示するには、サーバー **{guild.name}** のチャンネルで **{prefix}help** を使用してください。"
                                            f"プレフィックスを変更したい場合は **{prefix}setprefix** コマンドを使用してください"
                                            f"（**{prefix}setmyprefix** コマンドで個人用プレフィックスを設定することもできます）。"
                            ).set_image(url=image)
                        )

                        if bots_in_guild:

                            msg = f"サーバー **{guild.name}** にマルチボイスシステムと互換性のある他のボットがあることに気づきました: {', '.join(b.user.mention for b in bots_in_guild)}\n\n" \
                                   f"ボットがチャンネルに接続していない状態で音楽コマンド（例: play）を使用すると、サーバー内の空いているボットが使用されます。"

                            if not self.bot.pool.config.get("MULTIVOICE_VIDEO_DEMO_URL"):
                                embeds.append(
                                    disnake.Embed(
                                        color=color,
                                        description=msg
                                    ).set_image(url=image)
                                )

                            else:
                                send_video = msg

                        elif bots_outside_guild and self.bot.config.get('MULTIVOICE_VIDEO_DEMO_URL'):
                            send_video = "**サーバーで需要がある場合は、追加の音楽ボットを追加することもできます。\n" \
                                         "すべてのボットは同じプレフィックスとスラッシュコマンドを共有しているため、" \
                                         f"各ボットのプレフィックスやスラッシュコマンドを個別に覚える必要がありません。\n\n" \
                                         f"マルチボットの使用方法を示す[動画]({self.bot.config['MULTIVOICE_VIDEO_DEMO_URL']})をご覧ください。**"

                        if support_server:
                            embeds.append(disnake.Embed(color=color, description=support_server).set_image(url=image))

                        try:
                            await entry.user.send(embeds=embeds, components=components)
                            if send_video:
                                await asyncio.sleep(1)
                                await entry.user.send(send_video)
                            return
                        except disnake.Forbidden:
                            pass
                        except Exception:
                            traceback.print_exc()
                        break

        if not channel:

            for c in (guild.public_updates_channel, guild.rules_channel):

                if c and c.permissions_for(guild.me).send_messages:
                    channel = c
                    break

            if not channel:
                return

        embeds = [
            disnake.Embed(
                color=color, description="こんにちは！すべてのコマンドを表示するにはスラッシュ(**/**)を使用してください\n"
                                         "`注意: コマンドがサーバーに表示されない場合は、"
                                         "スラッシュコマンドを登録したボット/統合が50を超えている可能性があります。`"
            ).set_image(url=image)
        ]

        if prefix:
            prefix_msg = f"サーバーでの私のプレフィックスは: **{prefix}**"
        else:
            prefix = self.bot.default_prefix
            prefix_msg = f"私のデフォルトプレフィックスは **{prefix}**"

        embeds.append(
            disnake.Embed(
                color=color,
                description=f"プレフィックスによるテキストコマンドもあります。{prefix_msg}（私へのメンションもプレフィックスとして機能します）。"
                            f"すべてのテキストコマンドを表示するには **{prefix}help** を使用してください。"
                            f"プレフィックスを変更したい場合は **{prefix}setprefix** コマンドを使用してください"
                            f"（**{prefix}setmyprefix** コマンドで個人用プレフィックスを設定することもできます）。"
            ).set_image(url=image)
        )

        if bots_in_guild:

            msg = f"サーバー **{guild.name}** にマルチボイスシステムと互換性のある他のボットがあることに気づきました: {', '.join(b.user.mention for b in bots_in_guild)}\n\n" \
                  f"ボットがチャンネルに接続していない状態で音楽コマンド（例: play）を使用すると、" \
                   f"サーバー内の空いているボットが使用されます。"

            if not self.bot.config.get('MULTIVOICE_VIDEO_DEMO_URL'):
                embeds.append(
                    disnake.Embed(
                        color=color,
                        description=msg
                    ).set_image(url=image)
                )
            else:
                send_video = msg

        elif bots_outside_guild and self.bot.config.get('MULTIVOICE_VIDEO_DEMO_URL'):
            send_video = "**サーバーで需要がある場合は、追加の音楽ボットを追加することもできます。\n" \
                          "すべてのボットは同じプレフィックスとスラッシュコマンドを共有しているため、" \
                          f"各ボットのプレフィックスやスラッシュコマンドを個別に覚える必要がありません。\n\n" \
                        f"マルチボットの使用方法を示す[動画]({self.bot.config['MULTIVOICE_VIDEO_DEMO_URL']})をご覧ください。**"

        embeds.append(disnake.Embed(color=color, description=cmd_text).set_image(url=image))

        if support_server:
            embeds.append(disnake.Embed(color=color, description=support_server).set_image(url=image))

        kwargs = {"delete_after": 60} if channel == guild.rules_channel else {"delete_after": 300}

        timestamp = int((disnake.utils.utcnow() + datetime.timedelta(seconds=kwargs["delete_after"])).timestamp())

        embeds[-1].description += f"\nこのメッセージは <t:{timestamp}:R> に自動的に削除されます"

        try:
            await channel.send(embeds=embeds, components=components, **kwargs)
            if send_video:
                if "delete_after" in kwargs:
                    kwargs["delete_after"] = 600
                await asyncio.sleep(1)
                await channel.send(f"{send_video}\n\nこの機能を紹介する[**動画**]({self.bot.config['MULTIVOICE_VIDEO_DEMO_URL']})をご覧ください。", **kwargs)
        except:
            print(f"新しいサーバーのメッセージをチャンネルに送信できませんでした: {channel}\n"
                  f"チャンネルID: {channel.id}\n"
                  f"チャンネルタイプ: {type(channel)}\n"
                  f"{traceback.format_exc()}")


    about_cd = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.member)

    @commands.command(name="about", aliases=["sobre", "info", "botinfo"], description="私についての情報を表示します。",
                      cooldown=about_cd)
    async def about_legacy(self, ctx: CustomContext):
        await self.about.callback(self=self, interaction=ctx)


    @commands.slash_command(
        description=f"{desc_prefix}私についての情報を表示します。", cooldown=about_cd,
        extras={"allow_private": True}
    )
    @commands.contexts(guild=True)
    async def about(
            self,
            interaction: disnake.ApplicationCommandInteraction
    ):

        inter, bot = await select_bot_pool(interaction, first=True)

        if not bot:
            return

        await inter.response.defer(ephemeral=True)

        try:
            lavalink_ram = psutil.Process(self.bot.pool.lavalink_instance.pid).memory_info().rss
        except:
            lavalink_ram = 0

        python_ram = psutil.Process(getpid()).memory_info().rss

        ram_msg = f"> 🖥️ **⠂RAM使用量 (Python):** `{humanize.naturalsize(python_ram)}`\n"

        if lavalink_ram:
            ram_msg += f"> 🌋 **⠂RAM使用量 (Lavalink):** `{humanize.naturalsize(lavalink_ram)}`\n" \
                        f"> 🖥️ **⠂RAM使用量 (合計):** `{humanize.naturalsize(python_ram + lavalink_ram)}`\n"

        guild = bot.get_guild(inter.guild_id) or inter.guild

        try:
            color = bot.get_color(inter.guild.me if inter.guild else guild.me)
        except:
            color = bot.get_color()

        embed = disnake.Embed(description="", color=color)

        active_players_other_bots = 0
        inactive_players_other_bots = 0
        paused_players_other_bots = 0

        all_guilds_ids = set()

        allbots = self.bot.pool.get_all_bots()

        for b in allbots:
            for g in b.guilds:
                all_guilds_ids.add(g.id)

        guilds_size = len(all_guilds_ids)

        public_bot_count = 0
        private_bot_count = 0

        users = set()
        bots = set()
        listeners = set()

        user_count = 0
        bot_count = 0

        botpool_ids = [b.user.id for b in allbots]

        node_data = {}
        nodes_available = set()
        nodes_unavailable = set()

        for user in bot.users:
            if user.bot:
                bot_count += 1
            else:
                user_count += 1

        for b in allbots:

            for user in b.users:

                if user.id in botpool_ids:
                    continue

                if user.bot:
                    bots.add(user.id)
                else:
                    users.add(user.id)

            for n in b.music.nodes.values():

                if n.version == 0:
                    continue

                identifier = f"{n.identifier} (v{n.version})"

                if not identifier in node_data:
                    node_data[identifier] = {"total": 0, "available": 0, "website": n.website}

                node_data[identifier]["total"] += 1

                if n.is_available:
                    node_data[identifier]["available"] += 1

            for p in b.music.players.values():

                if not p.last_channel:
                    continue

                if p.auto_pause or not p.current:
                    inactive_players_other_bots += 1

                elif p.paused:
                    try:
                        if any(m for m in p.last_channel if not m.bot):
                            paused_players_other_bots += 1
                            continue
                    except (AttributeError, TypeError):
                        pass
                    inactive_players_other_bots += 1

                else:
                    active_players_other_bots += 1
                    for u in p.last_channel.members:
                        if u.bot or u.voice.deaf or u.voice.self_deaf:
                            continue
                        listeners.add(u.id)

            if not b.appinfo or not b.appinfo.bot_public:
                private_bot_count += 1
            else:
                public_bot_count += 1

        for identifier, data in node_data.items():

            if data["available"] > 0:
                if data['website']:
                    nodes_available.add(
                        f"> [`✅⠂{identifier}`]({data['website']}) `[{data['available']}/{data['total']}]`")
                else:
                    nodes_available.add(f"> `✅⠂{identifier} [{data['available']}/{data['total']}]`")
            else:
                nodes_unavailable.add(f"> `❌⠂{identifier}`")

        node_txt_final = "\n".join(nodes_available)

        if node_txt_final:
            node_txt_final += "\n"
        node_txt_final += "\n".join(nodes_unavailable)

        if len(allbots) < 2:

            embed.description += "### 統計 (現在のボット):\n" \
                                 f"> 🏙️ **⠂サーバー数:** `{(svcount:=len(bot.guilds)):,}`\n" \
                                 f"> 👥 **⠂ユーザー数:** `{user_count:,}`\n"

            if bot_count:
                embed.description += f"> 🤖 **⠂ボット数:** `{bot_count:,}`\n"

        else:

            embed.description += "### 統計 (全ボット合計):\n"

            if public_bot_count:
                embed.description += f"> 🤖 **⠂公開ボット数:** `{public_bot_count:,}`\n"

            if private_bot_count:
                embed.description += f"> 🤖 **⠂非公開ボット数:** `{private_bot_count:,}`\n"

            embed.description += f"> 🏙️ **⠂サーバー数:** `{guilds_size:,}`\n"

            if users_amount := len(users):
                embed.description += f"> 👥 **⠂ユーザー数:** `{users_amount:,}`\n"

            if bots_amount := len(bots):
                embed.description += f"> 🤖 **⠂ボット数:** `{bots_amount:,}`\n"

        embed.description += "### その他の情報:\n"

        if active_players_other_bots:
            embed.description += f"> ▶️ **⠂アクティブなプレーヤー:** `{active_players_other_bots:,}`\n"

        if paused_players_other_bots:
            embed.description += f"> ⏸️ **⠂一時停止中のプレーヤー:** `{paused_players_other_bots:,}`\n"

        if inactive_players_other_bots:
            embed.description += f"> 💤 **⠂非アクティブなプレーヤー:** `{inactive_players_other_bots:,}`\n"

        if listeners:
            embed.description += f"> 🎧 **⠂現在のリスナー:** `{(lcount:=len(listeners)):,}`\n"

        if bot.pool.commit:
            embed.description += f"> 📥 **⠂現在のコミット:** [`{bot.pool.commit[:7]}`]({bot.pool.remote_git_url}/commit/{bot.pool.commit})\n"

        embed.description += f"> 🐍 **⠂Pythonバージョン:** `{platform.python_version()}`\n" \
                             f"> 📦 **⠂Disnakeバージョン:** `{disnake.__version__}`\n" \
                             f"> 📶 **⠂レイテンシ:** `{round(bot.latency * 1000)}ms`\n" \
                             f"{ram_msg}" \
                             f"> ⏰ **⠂稼働時間:** <t:{int(bot.uptime.timestamp())}:R>\n"

        if not bot.config["INTERACTION_COMMAND_ONLY"]:

            guild_data = await bot.get_global_data(inter.guild_id, db_name=DBModel.guilds)

            if guild_data["prefix"]:
                embed.description += f"> ⌨️ **⠂サーバープレフィックス:** `{disnake.utils.escape_markdown(guild_data['prefix'], as_needed=True)}`\n"
            else:
                embed.description += f"> ⌨️ **⠂デフォルトプレフィックス:** `{disnake.utils.escape_markdown(bot.default_prefix, as_needed=True)}`\n"

            user_data = await bot.get_global_data(inter.author.id, db_name=DBModel.users)

            if user_data["custom_prefix"]:
                embed.description += f"> ⌨️ **⠂あなたのユーザープレフィックス:** `{disnake.utils.escape_markdown(user_data['custom_prefix'], as_needed=True)}`\n"

        links = "[`[ソース]`](https://github.com/zRitsu/MuseHeart-MusicBot)"

        if bot.config["SUPPORT_SERVER"]:
            links = f"[`[サポート]`]({bot.config['SUPPORT_SERVER']})  **|** {links}"

        embed.description += f"> 🌐 **⠂**{links}\n"

        try:
            owner = bot.appinfo.team.owner
        except AttributeError:
            owner = bot.appinfo.owner

        if node_txt_final:

            embed.description += f"### 音楽サーバー (Lavalink Servers):\n{node_txt_final}"

        try:
            avatar = owner.avatar.with_static_format("png").url
        except AttributeError:
            avatar = owner.default_avatar.with_static_format("png").url

        embed.set_footer(
            icon_url=avatar,
            text=f"オーナー: {owner} [{owner.id}]"
        )

        components = [disnake.ui.Button(custom_id="bot_invite", label="あなたのサーバーに追加")] if [b for b in self.bot.pool.bots if b.appinfo and (b.appinfo.bot_public or await b.is_owner(inter.author))] else None

        try:
            await inter.edit_original_message(embed=embed, components=components)
        except (AttributeError, disnake.InteractionNotEditable):
            try:
                await inter.response.edit_message(embed=embed, components=components)
            except:
                await inter.send(embed=embed, ephemeral=True, components=components)


    @commands.Cog.listener("on_button_click")
    async def invite_button(self, inter: disnake.MessageInteraction, is_command=False):

        if not is_command and inter.data.custom_id != "bot_invite":
            return

        bots_invites = []
        bots_in_guild = []

        guild = None

        if inter.guild_id:
            guild = inter.guild
        else:
            for bot in self.bot.pool.bots:
                if (guild:=bot.get_guild(inter.guild_id)):
                    break

        for bot in sorted(self.bot.pool.bots, key=lambda b: len(b.guilds)):

            try:
                if not bot.appinfo.bot_public and not await bot.is_owner(inter.author):
                    continue
            except:
                continue

            kwargs = {}

            invite = f"[`{disnake.utils.escape_markdown(str(bot.user.name))}`]({disnake.utils.oauth_url(bot.user.id, permissions=disnake.Permissions(bot.config['INVITE_PERMISSIONS']), scopes=('bot',), **kwargs)})"

            if bot.appinfo.flags.gateway_message_content_limited:
                invite += f" `[{len(bot.guilds)}/100]`"
            else:
                invite += f" `[{len(bot.guilds)}]`"

            if guild and inter.author.guild_permissions.manage_guild and bot.user in guild.members:
                bots_in_guild.append(invite)
            else:
                bots_invites.append(invite)

        txt = ""

        if bots_invites:
            txt += "## 利用可能な音楽ボット:\n"
            for i in disnake.utils.as_chunks(bots_invites, 2):
                txt += " | ".join(i) + "\n"
            txt += "\n"

        if bots_in_guild:
            txt += "## 現在のサーバーにある音楽ボット:\n"
            for i in disnake.utils.as_chunks(bots_in_guild, 2):
                txt += " | ".join(i) + "\n"

        if not txt:
            await inter.send(
                embed=disnake.Embed(
                    colour=self.bot.get_color(
                        inter.guild.me if inter.guild else guild.me if guild else None
                    ),
                    description="## 利用可能な公開ボットがありません...",
                ), ephemeral=True
            )
            return

        color = self.bot.get_color(inter.guild.me if inter.guild else guild.me if guild else None)

        embeds = [
            disnake.Embed(
                colour=self.bot.get_color(inter.guild.me if inter.guild else guild.me if guild else None),
                description=p, color=color
            ) for p in paginator(txt)
        ]

        await inter.send(embeds=embeds, ephemeral=True)


    @commands.command(name="invite", aliases=["convidar"], description="あなたのサーバーに追加するための招待リンクを表示します。")
    async def invite_legacy(self, ctx):
        await self.invite.callback(self=self, inter=ctx)


    @commands.slash_command(
        description=f"{desc_prefix}あなたのサーバーに追加するための招待リンクを表示します。",
        extras={"allow_private": True}
    )
    @commands.contexts(guild=True)
    async def invite(self, inter: disnake.ApplicationCommandInteraction):

        await inter.response.defer(ephemeral=True)

        await self.invite_button(inter, is_command=True)

    @commands.user_command(name=disnake.Localized("Avatar", data={disnake.Locale.pt_BR: "Avatar", disnake.Locale.ja: "アバター"}))
    async def avatar(self, inter: disnake.UserCommandInteraction):

        user = inter.target

        guild = None

        bot = self.bot

        for b in self.bot.pool.get_guild_bots(inter.guild_id):
            if (guild:=b.get_guild(inter.guild_id)):
                bot = b
                break

        if not guild:
            user = await bot.fetch_user(user.id)

            user_avatar_url = user.display_avatar.replace(static_format="png", size=512).url

            if user_banner_url:=user.banner:
                user_banner_url = user.banner.replace(static_format="png", size=4096).url

            guild_avatar_url = None
            guild_banner_url = None

        else:
            async with self.bot.session.get(f"https://discord.com/api/v10/guilds/{inter.guild_id}/members/{user.id}",
                                            headers={"Authorization": f"Bot {bot.http.token}"}) as r:
                data = await r.json()

            user_avatar_url = user.display_avatar.replace(static_format="png", size=512).url

            if user_banner_url := data['user'].get('banner'):
                user_banner_url = f"https://cdn.discordapp.com/banners/{user.id}/{user_banner_url}." + (
                    "gif" if user_banner_url.startswith('a_') else "png") + "?size=4096"

            if guild_avatar_url := data.get("avatar"):
                guild_avatar_url = f"https://cdn.discordapp.com/guilds/{inter.guild_id}/users/{user.id}/avatars/{guild_avatar_url}." + (
                    "gif" if guild_avatar_url.startswith('a_') else "png") + "?size=512"

            if guild_banner_url := data.get("banner"):
                guild_banner_url = f"https://cdn.discordapp.com/guilds/{inter.guild_id}/users/{user.id}/banners/{guild_banner_url}." + (
                    "gif" if guild_banner_url.startswith('a_') else "png") + "?size=4096"

        embeds = []

        requester = inter.author.display_avatar.with_static_format("png").url

        color = self.bot.get_color()

        if guild_avatar_url:
            embeds.append(
                disnake.Embed(
                    description=f"{user.mention} **[avatar (server)]({guild_avatar_url})**",
                    color=color).set_image(url=guild_avatar_url)
            )

        if guild_banner_url:
            embeds.append(
                disnake.Embed(
                    description=f"{user.mention} **[banner (server)]({guild_banner_url})**",
                    color=color).set_image(url=guild_banner_url)
            )

        embeds.append(
            disnake.Embed(
                description=f"{user.mention} **[avatar (user)]({user_avatar_url})**",
                color=color).set_image(url=user_avatar_url)
        )

        if user_banner_url:
            embeds.append(
                disnake.Embed(
                    description=f"{user.mention} **[banner (user)]({user_banner_url})**",
                    color=color).set_image(url=user_banner_url)
            )

        if inter.user.id != user.id:
            embeds[-1].set_footer(text=f"リクエスト者: {inter.author}", icon_url=requester)

        await inter.send(embeds=embeds, ephemeral=True)

    @commands.is_owner()
    @commands.max_concurrency(1, commands.BucketType.default)
    @commands.command(hidden=True, description="空白を含むお気に入りを修正するための一時的なコマンドです。"
                                               "これは特定の状況でエラーを引き起こす可能性があります。")
    async def fixfavs(self, ctx: CustomContext):

        if not os.path.isdir("./local_database/fixfavs_backup"):
            os.makedirs("./local_database/fixfavs_backup")

        async with ctx.typing():

            for bot in self.bot.pool.get_all_bots():

                db_data = await bot.pool.database.query_data(collection=str(bot.user.id), db_name=DBModel.guilds, limit=300)
    
                async with aiofiles.open(f"./local_database/fixfavs_backup/guild_favs_{bot.user.id}.json", "w") as f:
                    await f.write(json.dumps(db_data, indent=4))

                for data in db_data:
                    try:
                        remove_blank_spaces(data["player_controller"]["fav_links"])
                    except KeyError:
                        continue
                    await bot.update_data(id_=data["_id"], data=data, db_name=DBModel.guilds)

            db_data = await self.bot.pool.database.query_data(collection="global", db_name=DBModel.users, limit=500)

            async with aiofiles.open("./local_database/fixfavs_backup/user_favs.json", "w") as f:
                await f.write(json.dumps(db_data, indent=4))

            for data in db_data:
                remove_blank_spaces(data["fav_links"])
                await self.bot.update_global_data(id_=data["_id"], data=data, db_name=DBModel.users)

            await ctx.send("お気に入りが正常に修正されました！")

    async def cog_check(self, ctx):
        return await check_requester_channel(ctx)

    def cog_unload(self):

        try:
            self.task.cancel()
        except:
            pass


class GuildLog(commands.Cog):

    def __init__(self, bot: BotCore):
        self.bot = bot
        self.hook_url: str = ""

        if bot.config["BOT_ADD_REMOVE_LOG"]:

            if URL_REG.match(bot.config["BOT_ADD_REMOVE_LOG"]):
                self.hook_url = bot.config["BOT_ADD_REMOVE_LOG"]
            else:
                print("Webhookの URL が無効です（ボットの追加/削除ログの送信用）。")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: disnake.Guild):

        print(f"😭 - ボット {self.bot.user.name} がサーバーから削除されました: {guild.name} - [{guild.id}]")

        try:
            await self.bot.music.players[guild.id].destroy()
        except KeyError:
            pass
        except:
            traceback.print_exc()

        if not self.hook_url:
            return

        try:
            await self.send_hook(guild, title="サーバーから削除されました", color=disnake.Color.red())
        except:
            traceback.print_exc()

        await self.bot.update_appinfo()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: disnake.Guild):

        print(f"🎉 - ボット {self.bot.user.name} がサーバーに追加されました: {guild.name} - [{guild.id}]")

        try:
            guild_data = await self.bot.get_data(guild.id, db_name=DBModel.guilds)
            guild_data["player_controller"] = deepcopy(db_models[DBModel.guilds]["player_controller"])
            await self.bot.update_data(guild.id, guild_data, db_name=DBModel.guilds)
        except:
            traceback.print_exc()

        if not self.hook_url:
            return

        try:
            await self.send_hook(guild, title="新しいサーバーに追加されました", color=disnake.Color.green())
        except:
            traceback.print_exc()

        await self.bot.update_appinfo()

    async def send_hook(self, guild: disnake.Guild, title: str, color: disnake.Color):

        created_at = int(guild.created_at.timestamp())

        embed = disnake.Embed(
            description=f"__**{title}:**__\n"
                        f"```{guild.name}```\n"
                        f"**ID:** `{guild.id}`\n"
                        f"**オーナー:** `{guild.owner} [{guild.owner.id}]`\n"
                        f"**作成日:** <t:{created_at}:f> - <t:{created_at}:R>\n"
                        f"**認証レベル:** `{guild.verification_level or 'なし'}`\n"
                        f"**メンバー:** `{len([m for m in guild.members if not m.bot])}`\n"
                        f"**ボット:** `{len([m for m in guild.members if m.bot])}`\n",
            color=color
        )

        try:
            embed.set_thumbnail(url=guild.icon.replace(static_format="png").url)
        except AttributeError:
            pass

        if (channel:=self.bot.get_channel(self.bot.config["BOT_ADD_REMOVE_LOG_CHANNEL_ID"])) and channel.permissions_for(channel.guild.me).send_messages:
            await channel.send(
                ", ".join(f"<@{owner_id}>" for owner_id in self.bot.owner_ids) or self.bot.owner.mention,
                embed=embed
            )

        else:
            async with ClientSession() as session:
                webhook = disnake.Webhook.from_url(self.hook_url, session=session)
                await webhook.send(
                    content=", ".join(f"<@{owner_id}>" for owner_id in self.bot.owner_ids) or self.bot.owner.mention,
                    username=self.bot.user.name,
                    avatar_url=self.bot.user.display_avatar.replace(size=256, static_format="png").url,
                    embed=embed
                )


def setup(bot: BotCore):
    bot.add_cog(Misc(bot))
    bot.add_cog(GuildLog(bot))
