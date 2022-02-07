from typing import Callable, Dict, List

import discord


class Reaction_Callback:
    def __init__(self):
        # the callback is associated with a specific message
        self.msg_callback: Dict[int, Callable] = {}
        # the callback that is triggered whenever a reaction is triggered
        self.absolute_callback: List[Callable] = []
        # the callback that is only triggered when there's no msg_callback fitted
        self.residue_callback: List[Callable] = []

    def add_msg_callback(self, msg_id: int, callback: Callable):
        if msg_id in self.msg_callback:
            raise ValueError(f"A callback is already associated with msg with id '{msg_id}'")
        self.msg_callback[msg_id] = callback

    def remove_msg_callback(self, msg_id: int):
        msg_id = int(msg_id)
        if msg_id not in self.msg_callback:
            raise ValueError("inconsistency in database, no such msg_callback")
        del self.msg_callback[msg_id]

    def add_absolute_callback(self, callback: Callable):
        self.absolute_callback.append(callback)

    def add_residue_callback(self, callback: Callable):
        self.residue_callback.append(callback)

    async def on_reaction_happen(self, bot, payload: discord.RawReactionActionEvent):
        guild: discord.Guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        msg_id = payload.message_id
        if msg_id in self.msg_callback:
            await self.msg_callback[msg_id](payload, bot, member)
        else:
            for callback in self.residue_callback:
                await callback(payload, bot, member)

        for callback in self.absolute_callback:
            await callback(payload, bot, member)

