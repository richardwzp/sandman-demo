import random
import warnings
from typing import List, Callable, Dict, Tuple

import discord
import discord_slash
from discord.ext.commands import Cog
from discord_slash import cog_ext, SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option

from postgres_database import Sandman_Sql
from reaction import Reaction_Callback

default_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
emoji_limit = 10
guild_permission = {}
guilds = [709089549460045945, 753022598392053770]


def admin_permission(func):
    """The actual permission for the API is sort of stupid"""

    async def wrapper(self: 'MenuCog', ctx: discord_slash.SlashContext, *args, **kwargs):
        for role in ctx.author.roles:
            role: discord.role.Role = role
            # TODO: dangerous find a way to fix this
            # only respond if is admin
            if str(role.id) == self.servers[str(ctx.guild_id)][1]:
                return await func(self, ctx, *args, **kwargs)
        await ctx.send("you do not have the permission", hidden=True)
        return

    return wrapper


class MenuCog(Cog):
    def __init__(self, bot, database: Sandman_Sql, reaction_add_call_back, reaction_del_call_back):
        self.bot: discord.Client = bot
        self.database = database
        self.reaction_add_call_back: Reaction_Callback = reaction_add_call_back
        self.reaction_del_call_back: Reaction_Callback = reaction_del_call_back
        # (menu_msg_id -> Dict(emoji -> role))
        self.menu_cls_emoji_holder: Dict[str, Dict] = {}
        servers = self.database.get_all_servers()
        self.servers = {}
        if servers:
            for server in servers:
                # server_id: owner_id, admin_id, mod_id
                self.servers[server[0]] = server[1:]
        else:
            warnings.warn("there's no server currently connected to the bot")
        # self.ready()

    def ready(self):
        # check if there's any existing menus, if there is reactivate them
        menus = self.database.get_menus()
        for menu in menus:
            # TODO: this needs to be fixed, look at implementation too much
            classes = self.database.get_all_relationships_from_menu_group(menu[0])
            cls_emoji_dic = {}
            for cls in classes:
                role_id = int(cls[2])
                guild: discord.Guild = self.bot.get_guild(int(menu[3]))
                role = guild.get_role(role_id)
                cls_emoji_dic[cls[3]] = role
            self.reaction_add_call_back.add_msg_callback(
                int(menu[0]), self._create_react_add_callback(menu[0], cls_emoji_dic))
            self.reaction_del_call_back.add_msg_callback(
                int(menu[0]), self._create_react_remove_callback(menu[0], cls_emoji_dic))

    @cog_ext.cog_slash(
        name="create_menu_group",
        description="create a new menu group",
        guild_ids=guilds,
        options=[
            create_option("menu_name",
                          "the name of the menu",
                          SlashCommandOptionType.STRING,
                          required=True)])
    @admin_permission
    async def create_menu_group(self, ctx: discord_slash.SlashContext, menu_name):
        self.database.add_menu_group(menu_name, ctx.guild_id)
        self.database.commit_all()
        await ctx.send(f'created a menu with name "{menu_name}" and guild "{ctx.guild_id}"')

    @cog_ext.cog_slash(
        name="delete_menu_group",
        description="delete a new menu group",
        guild_ids=guilds,
        options=[
            create_option("menu_name",
                          "the name of the menu",
                          SlashCommandOptionType.STRING,
                          required=True)])
    @admin_permission
    async def delete_menu_group(self, ctx: discord_slash.SlashContext, menu_name):
        if not self.database.delete_menu_group(menu_name, ctx.guild_id):
            return await ctx.send(f'the menu "{menu_name}" didn\'t even exists')
        self.database.commit_all()
        await ctx.send(f'deleted a menu with name "{menu_name}" and guild "{ctx.guild_id}"')

    @cog_ext.cog_slash(
        name="add_class_to_menu",
        description="add a new class to menu",
        guild_ids=guilds,
        options=[
            create_option("menu_name",
                          "the name of the menu",
                          SlashCommandOptionType.STRING,
                          required=True),
            create_option("class_number",
                          "the number of the class i.e. (CS2500)",
                          SlashCommandOptionType.STRING,
                          required=True)])
    @admin_permission
    async def add_class_to_menu(self, ctx: discord_slash.SlashContext,
                                menu_name, class_number):
        await ctx.defer()
        class_number = class_number.upper()
        cls_obj = self.database.get_class(class_number, 'NEU')
        if not self.database.get_menu_group(menu_name, ctx.guild_id):
            return await ctx.send(f'menu "{menu_name}" does not exist yet')
        if not cls_obj:
            return await ctx.send(f'class "{class_number}" has not been created yet')
        if self.database.get_class_from_menu_group(menu_name, class_number):
            return await ctx.send(f'class "{class_number}" is already in the menu group')

        existing_menus = self.database.get_menus_from_group(menu_name, ctx.guild_id)
        if not existing_menus:
            self.database.add_class_to_menu_group(class_number, 'NEU', menu_name, ctx.guild_id)
            self.database.commit_all()
            await ctx.send(f'added class "{class_number}" to menu "{menu_name}"')
        else:
            # there's existing menus, therefore need to add the class to menu_group,
            # but also add the callbacks into existing menus
            menu_counter = 0
            menu_to_use_id = None
            current_cls_count = 0
            class_role_id = self.database.get_role_of_class(class_number, 'NEU')
            cls_role = ctx.guild.get_role(int(class_role_id))
            self.database.add_class_to_menu_group(class_number, 'NEU', menu_name, ctx.guild_id)
            for menu in existing_menus:
                # menu: menu_msg_id, channel_id, menu_group_name, server_id
                cls_count = self.database.class_count_in_menu(menu[0])
                if cls_count < emoji_limit:
                    menu_to_use_id = menu[0]
                    current_cls_count = cls_count
                    break

                menu_counter += 1
            if menu_to_use_id is None:
                # need a new menu, generate the menu
                # reactions are not added yet, that will happen later
                # currently it's just an empty menu
                cls_emoji_dic = {}
                menu_msg = await ctx.channel.send(
                    embed=self._create_base_class_menu_embed(menu_name + f": part {menu_counter + 1}"))
                menu_to_use_id = menu_msg.id
                self.menu_cls_emoji_holder[menu_to_use_id] = cls_emoji_dic
                self.reaction_add_call_back.add_msg_callback(
                    menu_to_use_id,
                    self._create_react_add_callback(menu_to_use_id, cls_emoji_dic))
                self.reaction_del_call_back.add_msg_callback(
                    menu_to_use_id,
                    self._create_react_remove_callback(menu_to_use_id, cls_emoji_dic))
            else:
                menu_msg = await ctx.channel.fetch_message(int(menu_to_use_id))




            # now do the book keeping for the roles, and add it to callbacks
            # TODO: still using default here
            self.database.add_class_to_menu(
                class_number,
                'NEU',
                class_role_id,
                default_emoji[current_cls_count],
                menu_to_use_id)
            # edit the dictionary callbacks used to add/remove roles
            self.menu_cls_emoji_holder[menu_to_use_id][default_emoji[current_cls_count]] = \
                cls_role

            # now add the reaction to the message, and edit it
            await menu_msg.add_reaction(default_emoji[current_cls_count])
            msg_embed = menu_msg.embeds[0]
            self._add_class_field_to_menu_embed(msg_embed,
                                                class_number,
                                                cls_obj[1],
                                                default_emoji[current_cls_count],
                                                cls_role)
            await menu_msg.edit(embed=msg_embed)
            await ctx.send('added new class to existing menu', delete_after=5)

            self.database.commit_all()



    @cog_ext.cog_slash(
        name="delete_class_from_menu",
        description="delete a class from an existing menu",
        guild_ids=guilds,
        options=[
            create_option("menu_name",
                          "the name of the menu",
                          SlashCommandOptionType.STRING,
                          required=True),
            create_option("class_number",
                          "the number of the class i.e. (CS2500)",
                          SlashCommandOptionType.STRING,
                          required=True)])
    @admin_permission
    async def delete_class_from_menu(self, ctx: discord_slash.SlashContext, menu_name, class_number):
        class_number = class_number.upper()
        if not self.database.get_menu_group(menu_name, ctx.guild_id):
            return await ctx.send(f'menu "{menu_name}" does not exist yet')
        if not self.database.get_class(class_number, 'NEU'):
            return await ctx.send(f'class "{class_number}" has not been created yet')
        if not self.database._database_get('CLASS_IN_MENU_GROUP',
                                           ['CLASS_NUMBER', 'SCHOOL_NAME'],
                                           [class_number, 'NEU']):
            return await ctx.send(f'the class "{class_number}" is not in the current menu group yet')

        self.database._database_delete('CLASS_IN_MENU_GROUP',
                                       ['CLASS_NUMBER', 'SCHOOL_NAME'],
                                       [class_number, 'NEU'])
        self.database.commit_all()

        return await ctx.send(f'successfully removed class "{class_number}" from menu {menu_name}')

    @cog_ext.cog_slash(
        name="generate_menu_messages",
        description="generate an interactive reaction message base on a menu group",
        guild_ids=guilds,
        options=[
            create_option("menu_name",
                          "the name of the menu",
                          SlashCommandOptionType.STRING,
                          required=True)])
    @admin_permission
    async def generate_menu_message(self, ctx: discord_slash.SlashContext, menu_name):
        # TODO: for now only generate a class menu

        if not self.database.get_menu_group(menu_name, ctx.guild_id):
            return await ctx.send(f'menu group "{menu_name}" does not exist yet')

        generation_wait_msg = await ctx.send("generation starts", delete_after=1)

        classes = self.database.get_classes_from_menu_group(menu_name)
        class_with_role = []
        for cls in classes:
            role: discord.Role = ctx.guild.get_role(int(self.database.get_role_of_class(cls[0], 'NEU')))
            if not role:
                await generation_wait_msg.delete()
                return await ctx.send(f'class "{cls[0]}" does not have role associated yet')
            class_with_role.append([*cls, role])

            # menu_embed.add_field(name=cls[0], value=cls[1] + ": " + role.mention, inline=False)
            # menu_embed.description = "listing all classes"

        partitioned_cls = self.class_partition(class_with_role)

        # now generate the menu for each group
        for index, menu_group in enumerate(partitioned_cls):
            menu_title = menu_name if len(partitioned_cls) == 1 else menu_name + f": part {index + 1}"
            menu_embed = self._create_base_class_menu_embed(menu_title)
            menu_msg = await ctx.channel.send(embed=discord.embeds.Embed(
                title=menu_title,
                description="generating menu",
            ))
            # create the menu, associated with a message and a channel
            self.database.add_menu(str(menu_msg.id), str(ctx.channel_id), menu_name, ctx.guild_id)

            cls_emoji_dic = {}
            for cls in menu_group:
                class_name, class_full_name, cls_emoji, cls_role = cls[0], cls[1], cls[-1], cls[-2]
                self._add_class_field_to_menu_embed(menu_embed, class_name, class_full_name, cls_emoji, cls_role)
                await menu_msg.add_reaction(cls_emoji)
                cls_emoji_dic[cls_emoji] = cls_role
                # create associated in database of class to menu
                self.database.add_class_to_menu(class_name, 'NEU', str(cls_role.id), cls_emoji, str(menu_msg.id))

            # create the callback needed to add roles
            self.reaction_add_call_back.add_msg_callback(
                menu_msg.id,
                self._create_react_add_callback(menu_msg.id, cls_emoji_dic))
            self.reaction_del_call_back.add_msg_callback(
                menu_msg.id,
                self._create_react_remove_callback(menu_msg.id, cls_emoji_dic))

            await menu_msg.edit(embed=menu_embed)

        self.database.commit_all()
        await generation_wait_msg.delete()

    @staticmethod
    def _create_base_class_menu_embed(menu_name, description=None):
        return discord.embeds.Embed(
            title=menu_name,
            description="react to the corresponding emoji to obtain role" if description is None else description)

    @staticmethod
    def _add_class_field_to_menu_embed(menu_embed: discord.Embed,
                                       class_name: str,
                                       class_full_name: str,
                                       cls_emoji: str,
                                       cls_role: discord.Role):
        menu_embed.add_field(name=f"`{class_name + ' (' + class_full_name + ')'}`",
                             value=f"{cls_emoji} {' - ' * 45} {cls_role.mention}"
                                   f"\n\u2800",
                             inline=False)

    def _create_react_add_callback(self, msg_id: str, cls_emoji_dic: Dict) -> \
            Callable:
        self.menu_cls_emoji_holder[str(msg_id)] = cls_emoji_dic

        async def callback(payload: discord.RawReactionActionEvent, bot, member: discord.Member):
            if payload.message_id != int(msg_id) or member.bot:
                return
            if payload.emoji.name in cls_emoji_dic:

                await member.add_roles(cls_emoji_dic[payload.emoji.name],
                                       reason="added role base on reaction")
            # default behavior for reacting, this can also be added with an
            # agreed upon symbol for all other emoji unrecognized
            else:
                msg: discord.Message = await bot \
                    .get_channel(payload.channel_id) \
                    .fetch_message(payload.message_id)
                await msg.remove_reaction(payload.emoji, member)

        return callback

    def _create_react_remove_callback(self, msg_id: str, cls_emoji_dic: Dict) -> \
            Callable:
        async def del_callback(reaction: discord.RawReactionActionEvent, bot, member: discord.Member):
            if reaction.message_id != int(msg_id) or member.bot:
                return
            else:
                try:
                    reaction_emo = reaction.emoji.name
                    await member.remove_roles(cls_emoji_dic[reaction_emo],
                                              reason="deleted role base on reaction")
                except KeyError as e:
                    print(e)
                    # a faulty emo removal, most liekly triggered by the bot
                    # no idea how to prevent, so ignore
                    pass

        return del_callback

    def class_partition(self, classes: List):
        partitioned_classes: List[List] = []
        individual_partition: List = []
        emoji_iter = iter(default_emoji)
        for cls in classes:

            if len(individual_partition) < emoji_limit:
                individual_partition.append([*cls, next(emoji_iter)])
            else:
                emoji_iter = iter(default_emoji)
                partitioned_classes.append(individual_partition)
                individual_partition = [[*cls, next(emoji_iter)]]

        # if there's residual, append it
        if individual_partition:
            partitioned_classes.append(individual_partition)

        return partitioned_classes

    @cog_ext.cog_slash(
        name="cancel_menu_group",
        description="cancel an activated menu group, could be multiple menu messages",
        guild_ids=guilds,
        options=[
            create_option("menu_name",
                          "the name of the menu",
                          SlashCommandOptionType.STRING,
                          required=True)])
    @admin_permission
    async def cancel_menu_group(self, ctx: discord_slash.SlashContext, menu_name):
        if not self.database.get_menu_group(menu_name, ctx.guild_id):
            return await ctx.send(f"the menu group '{menu_name}' does not exist yet")

        active_menus = self.database.get_menus_from_group(menu_name, ctx.guild_id)
        if not active_menus:
            return await ctx.send(f'the menu group "{menu_name}" does not have any active menu yet')

        # delete all callbacks that exists, and clean database
        for menu in active_menus:
            menu_msg_id = menu[0]
            # clean database
            self.database.delete_classes_in_menu(menu_msg_id)
            self.database.delete_menu(menu_msg_id, ctx.guild_id)
            self.database.commit_all()

            self.reaction_add_call_back.remove_msg_callback(menu_msg_id)
            self.reaction_del_call_back.remove_msg_callback(menu_msg_id)

        return await ctx.send(f'for menu group "{menu_name}", deactivated {len(active_menus)} menus')

    @cog_ext.cog_slash(
        name="create_class",
        description="create a new class",
        guild_ids=guilds,
        options=[
            create_option("class_number",
                          "the number of the class i.e. (CS2500)",
                          SlashCommandOptionType.STRING,
                          required=True),
            create_option("class_full_name",
                          "the name of the menu",
                          SlashCommandOptionType.STRING,
                          required=True),
            create_option("description",
                          "a description of the class",
                          SlashCommandOptionType.STRING,
                          required=False),
            create_option("student_role",
                          "student role associated with this class",
                          SlashCommandOptionType.ROLE,
                          required=False),
            create_option("ta_role",
                          "ta role associated with this class",
                          SlashCommandOptionType.ROLE,
                          required=False),
            create_option("category",
                          "ta role associated with this class",
                          SlashCommandOptionType.CHANNEL,
                          required=False)])
    @admin_permission
    async def create_class(self, ctx: discord_slash.SlashContext,
                           class_number, class_full_name, description="", student_role=None, ta_role=None,
                           category: discord.CategoryChannel = None):
        class_number = class_number.upper()
        if category is not None and category.type != discord.ChannelType.category:
            return await ctx.send("given category is a non category channel")

        if self.database.get_class(class_number, 'NEU'):
            return await ctx.send(f"class '{class_number}' already exists")

        self.database.add_class(class_number, class_full_name, 'NEU', description)
        if student_role is None:
            student_role: discord.Role = await ctx.guild.create_role(reason="role created through class creation",
                                                                     name=class_number.upper(),
                                                                     colour=discord.Colour.from_rgb(
                                                                         random.randint(0, 255),
                                                                         random.randint(0, 255),
                                                                         random.randint(0, 255)))

        if ta_role is None:
            ta_role: discord.Role = await ctx.guild.create_role(reason="role created through class creation",
                                                                name=class_number.upper() + " TA",
                                                                colour=student_role.colour)

        await ctx.send(f"start creating category '{class_number}'")
        if category is None:
            # create the category, only the class associated can see
            guild = ctx.guild
            category = await guild.create_category_channel(name=class_number,
                                                           reason='a new class is created with this category')
            # @everyone cannot see the category
            await category.set_permissions(target=guild.get_role(ctx.guild_id),
                                           reason='can not be accessed by everyone',
                                           read_messages=False)
            await category.set_permissions(target=guild.get_role(student_role.id),
                                           reason='student of the course can see it',
                                           read_messages=True)
            await category.set_permissions(target=guild.get_role(ta_role.id),
                                           reason='ta of the course can see it',
                                           read_messages=True)

            announcement = await category.create_text_channel(name=class_number + '-announcement')
            await announcement.edit(sync_permissions=True)
            await announcement.edit(slowmode_delay=6 * 60 * 60)

            general = await category.create_text_channel(name=class_number + '-general')
            await general.edit(sync_permissions=True)

            general = await category.create_voice_channel(name='study group 1')
            await general.edit(sync_permissions=True)

            general = await category.create_voice_channel(name='study group 2')
            await general.edit(sync_permissions=True)

        self.database.add_class_role(class_number, 'NEU', student_role.id)
        self.database.add_ta_role(class_number, 'NEU', ta_role.id)
        self.database.commit_all()

        return await ctx.channel.send(f"created new class '{class_number}'")


if __name__ == '__main__':
    pass
