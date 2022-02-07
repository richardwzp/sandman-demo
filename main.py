import json
from random import randint
from typing import Dict, Tuple, Any, Callable, Coroutine

import discord
from discord import Colour
from discord.ext import commands
from discord_slash import SlashCommand
from discord_slash.utils.manage_commands import create_option, create_choice, create_permission
from discord_slash.model import SlashCommandPermissionType
from re import search

import moderation
import role_menu_v2
import starboard
from postgres_database import Sandman_Sql, open_sandman_database
from reaction import Reaction_Callback
from moderation import ModerationCog
description = '''An example bot to showcase the discord.ext.commands extension
module.
There are a number of utility commands being showcased here.'''

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='?', description=description, intents=intents)
activity = discord.Activity(type=discord.ActivityType.watching, name="the server ⏳")
slash = SlashCommand(bot, sync_commands=True)

# khoury student group
#guild_id = [753022598392053770]
#admin_id = [753028535404331039]


# testing server, khoury
guild_id = [709089549460045945, 753022598392053770]
admin_id = [838875682792407060, 753028535404331039]
# TODO: dangerous to do
menu_cog = None

# functionalities:

# TODO: give someone the ability moderate a specific category

# TODO: able to add channel at specific place
# TODO:


@bot.event
async def on_ready():
    category = []
    for i in bot.get_all_channels():

        if i.type == discord.ChannelType.category:
            category.append(i.text_channels)
    await bot.change_presence(activity=activity, status=discord.Status.do_not_disturb)
    print('Logged in as')
    print(bot.user.name)
    print('-------------------')
    menu_cog.ready()


# any command that require a mod to run
slash_permission = slash.permission(guild_id=guild_id[0],
                                    permissions=[
                                        create_permission(admin_id[0], SlashCommandPermissionType.ROLE, True),
                                        create_permission(guild_id[0], SlashCommandPermissionType.ROLE, False)
                                    ])
category_option = create_option(
    name="category",
    description="category that is associated with the given",
    option_type=7,
    required=True)
role_option = create_option(
    name="role",
    description="role to be used",
    option_type=8,
    required=True)
class_option = create_option(
    name="class_name",
    description="the name of the class to spawn",
    option_type=3,
    required=True)
member_option = create_option(
    name="member",
    description="member to be selected",
    option_type=6,
    required=True)


@slash.slash(name="archive", description="""
Arhive a given channel. remove all existing member with the given role. 
""", options=[category_option, role_option], guild_ids=guild_id)
@slash_permission
async def _archive(ctx, category, role):
    if type(category) != discord.channel.CategoryChannel:
        await ctx.send("expected a category, received a text channel")
        return
    category_name = category.name
    if search("-\(archived\)", category_name):
        await ctx.send('the given category is already archived')
        return
    await category.edit(name=category_name + "-(archived)",
                        reason=f"{category_name} is archived")
    await category.set_permissions(target=role,
                                   view_channel=False,
                                   reason=f"{role} can now access the category")
    await ctx.send(f"success! {category_name} has been archived.")


@slash.slash(name="unarchive", description="""
Unarhive a given channel. Give associated role the permission to view.
""", options=[category_option, role_option], guild_ids=guild_id)
@slash_permission
async def _unarchive(ctx, category, role):
    if type(category) != discord.channel.CategoryChannel:
        await ctx.send("expected a category, received a text channel")
        return

    category_name = category.name
    search_result = search("-\(archived\)", category_name)
    if not search_result:
        await ctx.send('the given category is not archived')
        return

    await category.edit(name=category_name[0: search_result.start()],
                        reason=f"{category_name} is archived")
    await category.set_permissions(target=role,
                                   view_channel=True,
                                   reason=f"{role} now lost access to category")

    await ctx.send(f"success! {category.name} has been unarchived.")


@slash.slash(name="spawnClass", description="""
create a new category for the given class name.
also create the corresponding role.
""", options=[class_option], guild_ids=guild_id)
@slash_permission
async def _spawn_class(ctx, class_name):
    guild = ctx.guild
    new_role = await guild.create_role(name=class_name,
                                       colour=Colour.from_rgb(
                                           randint(0, 255), randint(0, 255), randint(0, 255)))
    permission = discord.PermissionOverwrite()
    permission.update(view_channel=True)
    everyone_permission = discord.PermissionOverwrite()
    everyone_permission.update(view_channel=False)
    everyone = guild.default_role
    new_category = await guild.create_category_channel(name=class_name,
                                                       overwrites={
                                                           new_role: permission,
                                                           everyone: everyone_permission},
                                                       reason=None,
                                                       position=None)
    announcement = await new_category.create_text_channel(name=class_name + "-announcement")
    await announcement.edit(slowmode_delay=6 * 60 * 60)

    general = await new_category.create_text_channel(name=class_name + "-general")
    study_group1 = await new_category.create_voice_channel(name="study-group-1")
    study_group1 = await new_category.create_voice_channel(name="study-group-2")

    await ctx.send(class_name)


@slash.slash(name="strip", description="""
strip the role away from all users.
""", options=[role_option], guild_ids=guild_id)
@slash_permission
async def _strip(ctx, role):
    await ctx.defer()
    for member in role.members:
        await member.remove_roles(role)

    await ctx.send('role has been stripped from all members')


@slash.slash(name="ta", description="""
make a user a ta in a specific class
""", options=[member_option, category_option, role_option,
              create_option(
                  name="ta_role",
                  description="optional TA role. if it's not provided, a new one is created",
                  option_type=8,
                  required=False)], guild_ids=guild_id)
@slash_permission
async def _ta(ctx, member, category, role, ta_role=None):
    guild = ctx.guild
    if not ta_role:
        ta_role = await guild.create_role(name=role.name + " TA",
                                          colour=role.colour)
    permission = discord.PermissionOverwrite()
    permission.update(view_channel=True)
    await category.set_permissions(ta_role, overwrite=permission)

    await member.add_roles(ta_role)

    await ctx.send("added ta role for " + member.name + ", class " + role.name)


@slash.slash(name="hemann", description="""
make sure the bot is working
""", guild_ids=guild_id)
async def _ping(ctx):
    await ctx.send(
        "I'm not naturally great with names. But I try really hard at it and I'm pretty relentless at asking for them when I don't know it. I suppose it's possible you were there and vocal and active and it's just blanked out of my memory. That's unfalsifiable. But I think 13 out of 15 in terms of class participation when I wouldn't recognize you on the back of a milk carton is fairly generous.\n \n --JBH")


@slash.slash(name="lerner", description="""
make sure the bot is working
""", guild_ids=guild_id)
async def _lerner(ctx):
    await ctx.send(
        "Giving 🙄  you 🙇😱 further 😠 examples would 💢  defeat the 👏😟 purpose of 👉 the question, which is for you ☝️  read and 👏👏 figure out 😲 what it means, and what it’s 💯✋ asking ❔😭 for, 😡 so 💁that you can 📑 solve the ⚕🕑 problem. Asking ❔ someone else 🤷😯 to work 🏢 through 👉🤢 the ❌  examples for you is like 🙄  asking 💬 them 🖋️ to go 🏃 to 😀 the 🏋️‍♂️  gym 💪 for 👏 you: 😣 they’ll 😄🙎 get 🙄 the benefit 😩 of the 👏 exercise, 🤸 and 😡 you ☝won’t. :lerner:")


@slash.slash(name="lerner2", description="""
make sure the bot is working
""", guild_ids=guild_id)
async def _lerner2(ctx):
    await ctx.send("""Let me gently suggest that this is a bad question to ask, especially in advance of the exam. The typical meaning students want for “curving an exam” is simply “give us more points even if we got things wrong”, aka grade inflation. The actual meaning of “curving an exam” is to force the exam grades to conform to a specific grade distribution (a pre-specified average and standard deviation, such that the histogram of grades forms a particular pre-chosen curvy shape), aka grade deflation. Neither of those is a pedagogically good outcome.

We’ve written enough exams over the years that we can calibrate the exam to be “roughly the same difficulty” as preceding years’ exams, and we know roughly how those grades turned out. And if the grades this year turn out roughly the same, then we won’t be artificially changing the grades for you at all. Ideally, an “80% on the exam” (just to pick a number) means you’ve mastered 80% of what we’ve taught so far. Changing the grades by artificially inflating or deflating them decouples their value from any meaningful feedback you could get from them, other than a good feeling for “getting a high number”.

Amal and I are perfectly happy for all of you to earn 100%s on the exam (we’d be delighted if everyone mastered everything we’ve taught!), and are perfectly willing to give out 0%s if those grades were earned (we’d be very disappointed, and it’s exceedingly unlikely, but it could happen). The only reason she or I ever modify the grades of an exam is if we recognize that a question was typoed, broken, or somehow much harder than intended and practically everyone gets it wrong for some reason or another, and we have to rectify a mistake that we made. And there’s absolutely no way for us to know that in advance of grading the exam!""")


@slash.slash(name="shiver", description="""
make sure the bot is working
""", guild_ids=guild_id)
async def _shiver(ctx):
    await ctx.send("""Who should I thank? My so-called "colleagues," who laugh at me behind my back, all the while becoming famous on my work? My worthless graduate students, whose computer skills appear to be limited to downloading bitmaps off of netnews? My parents, who are still waiting for me to quit fooling around with computers, go to med school, and become a radiologist? My department chairman, a manager who gives one new insight into and sympathy for disgruntled postal workers?

My God, no one could blame me -- no one! -- if I went off the edge and just lost it completely one day. I couldn't get through the day as it is without the Prozac and Jack Daniels I keep on the shelf, behind my Tops-20 JSYS manuals. I start getting the shakes real bad around 10am, right before my advisor meetings. A 10 oz. Jack 'n Zac helps me get through the meetings without one of my students winding up with his severed head in a bowling-ball bag. They look at me funny; they think I twitch a lot. I'm not twitching. I'm controlling my impulse to snag my 9mm Sig-Sauer out from my day-pack and make a few strong points about the quality of undergraduate education in Amerika.

If I thought anyone cared, if I thought anyone would even be reading this, I'd probably make an effort to keep up appearances until the last possible moment. But no one does, and no one will. So I can pretty much say exactly what I think.

Oh, yes, the acknowledgments. I think not. I did it. I did it all, by myself.""")


@slash.slash(name="shesh", description="""
hw over thanksgiving?
""", guild_ids=guild_id)
async def _shiver(ctx):
    await ctx.send("""I struggle to think of even one situation  where a company would move a release deadline because of the personal, optional travel plans of its engineers.

This serves as a reminder to me that perhaps trying to be understanding and pushing deadlines benefits nobody. It seems that being accommodating creates the expectation of even more accommodation. Lesson learned.""")

# (msg_id) -> Callable
reaction_add_call_back: Reaction_Callback = Reaction_Callback()
reaction_del_call_back: Reaction_Callback = Reaction_Callback()


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    await reaction_add_call_back.on_reaction_happen(bot, payload)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    await reaction_del_call_back.on_reaction_happen(bot, payload)

if __name__ == '__main__':
    with Sandman_Sql(open_sandman_database()) as database:
        with open("secre.tjson") as f:
            token = json.loads(f.read())['token']
        menu_cog = role_menu_v2.MenuCog(bot, database, reaction_add_call_back, reaction_del_call_back)
        #bot.add_cog(menu_cog)
        bot.add_cog(menu_cog)

        bot.add_cog(ModerationCog(bot, database, reaction_add_call_back, reaction_del_call_back))
        bot.add_cog(starboard.StarBoard(
            bot,
            database,
            reaction_add_call_back,
            reaction_del_call_back,
            count=6))
        bot.run(token)
