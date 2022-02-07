import datetime
import json
from typing import List, Callable

import discord
from discord.ext.commands import Cog
from discord_slash import cog_ext

from postgres_database import Sandman_Sql
from reaction import Reaction_Callback

class StarBoard(Cog):
    def __init__(self, bot,
                 database: Sandman_Sql,
                 reaction_add_call_back: Reaction_Callback,
                 reaction_del_call_back: Reaction_Callback,
                 count=6):
        self.bot = bot
        self.reaction_add_call_back = reaction_add_call_back
        self.reaction_del_call_back = reaction_del_call_back
        self.count = count
        self.database = database

        # add the messaging to the call_back
        self.reaction_add_call_back.add_residue_callback(self._on_reaction)

    async def _on_reaction(self, payload: discord.RawReactionActionEvent, _bot, _: discord.Member):
        msg: discord.Message = await self.bot \
            .get_channel(payload.channel_id) \
            .fetch_message(payload.message_id)

        if msg.author.bot:
            return

        if self.database.get_star_msg(msg.id):
            return
        reaction: discord.Reaction = discord.utils.get(msg.reactions, emoji=payload.emoji)
        if not reaction:
            # TODO: problem with default, two pass inefficient, fix at some point
            reaction = discord.utils.get(msg.reactions, emoji=payload.emoji.name)

        # for now, only use david_star
        if reaction.emoji != "✡️":
            return

        # if one reaction is from the sender, ignore it
        reaction_count = reaction.count if payload.user_id != msg.author.id else reaction.count - 1
        if reaction_count >= self.count:
            server_id = payload.guild_id
            board_name, channel_id, _ = self.database.get_starboard('funny-quotes', server_id)
            board_channel = self.bot.get_channel(int(channel_id))

            author: discord.Member = msg.author
            embedded = self.create_embed_board(msg, msg.author)
            # TODO: hardcoded funny-quotes
            self.database.add_starboard_msg('funny-quotes', msg.id, server_id)
            if embedded:
                await board_channel.send(content=f"✡️ {msg.channel.mention} | {author.mention}",
                                         embed=embedded)
            self.database.commit_all()

    @staticmethod
    def create_embed_board(message: discord.Message, member: discord.Member):
        msg = message.content
        attachments = message.attachments

        msg_body = msg if len(msg) <= 500 else msg[:500] + "..."
        today = datetime.date.today()
        embeded_element: discord.embeds.Embed = discord.embeds.Embed(
            title="",
            description=msg_body,
            colour=discord.Colour.from_rgb(255, 255, 255)) \
            .set_author(name=member.display_name, icon_url=member.avatar_url) \
            .add_field(name=f"\u2800", value=f'[**click to jump to this message!**]({message.jump_url})') \
            .set_footer(text=f"MessageID: {message.id} • {today.month}/{today.day}/{today.year}")
        if attachments and "image" in attachments[0].content_type:
            embeded_element.set_image(url=attachments[0])
        elif attachments:
            # TODO: attachment of weird type, we can do something abt it?
            return None
        return embeded_element
