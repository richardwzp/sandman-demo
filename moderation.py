import datetime
import random
import warnings

import discord
import discord_slash
from discord.ext.commands import Cog
from discord_slash import cog_ext, SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option

from postgres_database import Sandman_Sql
from reaction import Reaction_Callback

guilds = [709089549460045945, 753022598392053770]


def mod_permission(func):
    """The actual permission for the API is sort of stupid"""

    async def wrapper(self: 'ModerationCog', ctx: discord_slash.SlashContext, *args, **kwargs):
        for role in ctx.author.roles:
            role: discord.role.Role = role
            # TODO: dangerous find a way to fix this
            # only respond if is admin
            if str(role.id) == self.servers[str(ctx.guild_id)][1] or str(role.id) == self.servers[str(ctx.guild_id)][2]:
                return await func(self, ctx, *args, **kwargs)
        await ctx.send("you do not have the permission", hidden=True)
        return

    return wrapper


def mod_permission_no_arg(func):
    """The actual permission for the API is sort of stupid"""

    async def wrapper(self: 'ModerationCog', ctx: discord_slash.SlashContext):
        for role in ctx.author.roles:
            role: discord.role.Role = role
            # TODO: dangerous find a way to fix this
            # only respond if is admin
            if str(role.id) == self.servers[str(ctx.guild_id)][1] or str(role.id) == self.servers[str(ctx.guild_id)][2]:
                return await func(self, ctx)
        await ctx.send("you do not have the permission", hidden=True)
        return

    return wrapper


class ModerationCog(Cog):
    def __init__(self, bot, database: Sandman_Sql, reaction_add_call_back, reaction_del_call_back):
        self.bot: discord.Client = bot
        self.database = database
        self.reaction_add_call_back: Reaction_Callback = reaction_add_call_back
        self.reaction_del_call_back: Reaction_Callback = reaction_del_call_back

        servers = self.database.get_all_servers()
        self.servers = {}
        if servers:
            for server in servers:
                # server_id: owner_id, admin_id, mod_id
                self.servers[server[0]] = server[1:]
        else:
            warnings.warn("there's no server currently connected to the bot")
        # self.ready()

    @cog_ext.cog_slash(
        name="announce",
        description="create an announcement message",
        guild_ids=guilds,
        options=[
            create_option("message_id",
                          "the message to be sent, must be from the same channel",
                          SlashCommandOptionType.STRING,
                          required=True),
            create_option("ping",
                          "if this is true, ping everyone at the start",
                          SlashCommandOptionType.BOOLEAN,
                          required=False)])
    @mod_permission
    async def announce(self, ctx: discord_slash.SlashContext, message_id: str, ping: bool = False):
        try:
            msg = await ctx.channel.fetch_message(int(message_id))
        except discord.NotFound as e:
            return await ctx.send('the announcement msg with given id does not exist', hidden=True)
        await ctx.send('creating announcement', delete_after=1)
        msg_author: discord.Member = msg.author
        embed_announcement = discord.embeds.Embed()
        # today = datetime.date.today()
        # now = datetime.datetime.now()
        # current_time = "{:02d}:{:02d}".format(now.hour, now.minute)
        embed_announcement.set_author(name=msg_author.display_name,
                                      icon_url=msg_author.avatar_url)
        everyone: discord.Role = ctx.guild.get_role(ctx.guild_id)
        embed_announcement.add_field(
            name='\u2800',
            value=msg.content)
        embed_announcement.add_field(name='\u2800', value='\n\u2800\n\u2800')
        embed_announcement.colour = discord.Colour.from_rgb(
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255))
        if msg.attachments and "image" in msg.attachments[0].content_type:
            embed_announcement.set_image(url=msg.attachments[0])

        # honestly, I don't like it
        # embed_announcement.set_footer(text=f"{current_time} " + " " * 161 + f"{today.month}/{today.day}/{today.year}")
        await ctx.channel.send(content='@everyone' if ping else '' , embed=embed_announcement)
        await msg.delete()

    @cog_ext.cog_slash(
        name="strip_all_class_role",
        description="strip class roles from everyone, including ta roles",
        guild_ids=guilds,
        options=[])
    @mod_permission_no_arg
    async def strip_all_class_role(self, ctx: discord_slash.SlashContext):
        await ctx.defer()
        class_roles = self.database.get_all_roles()
        for role in class_roles:
            role_id = role[2]
            server_role: discord.Role = ctx.guild.get_role(int(role_id))
            for member in server_role.members:
                member: discord.Member = member
                await member.remove_roles(server_role, reason='mass role strip', atomic=True)
            await ctx.channel.send(f'finished stripping all member from {server_role.mention}')

        await ctx.send('all roles finished')