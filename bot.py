import json
from difflib import SequenceMatcher
from itertools import cycle
from os import environ, getenv, mkdir
from os.path import isfile, isdir
from pathlib import Path
from re import fullmatch
from textwrap import TextWrapper
from typing import Union

import discord
import requests
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Initialize variables
intents = discord.Intents.default()
intents.members = True
client = commands.Bot(command_prefix="w!", guild_subscriptions=True, intents=intents)
hc = 0x00c9ff
client.remove_command('help')

# Load env values
if "BOT_TOKEN" not in environ:
    env_path = Path(".") / ".env"
    load_dotenv(dotenv_path=env_path)
BOT_TOKEN = getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    print("Can't get bot token")
    exit()

# Check and create data files
if not isdir("data"):
    mkdir("data")
if not isfile("data/users.json"):
    with open("data/users.json", "w") as f:
        json.dump({}, f, indent=2)
if not isfile("data/settings.json"):
    with open("data/settings.json", "w") as f:
        json.dump({"request_channel": "", "status_loop": [], "author_id": ""}, f, indent=2)
    print("Please fill out settings file before proceeding")
    exit()

# Load settings
with open("data/settings.json") as f:
    settings = json.load(f)
    for i in settings.values():
        if len(i) < 1:
            print("Please fill out the settings")
            exit()
status = cycle(["Developed by BLANK"] + settings["status_loop"])


def get_username(uuid):
    """Get the username of a player from the UUID"""
    r = requests.get("https://api.mojang.com/user/profiles/{}/names".format(uuid))
    if r.ok and r.status_code not in [204, 400]:
        return r.json()[-1]["name"]
    else:
        if r.status_code in [204, 400]:
            raise ValueError("User not found")
        else:
            raise Exception("Can't reach Mojang API")


@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.online)
    change_status.start()
    print("Bot Started")


@tasks.loop(seconds=10)
async def change_status():
    await client.change_presence(activity=discord.Game(next(status)))


@client.event
async def on_member_remove(member):
    # Load data
    with open("data/users.json") as f:
        users = json.load(f)
    # Check if user is not whitelisted
    if str(member.id) not in users:
        return  # Don't need to do anything if they weren't part of whitelist system
    else:
        usr = users[str(member.id)]
        del users[str(member.id)]
        # Write JSON file
        with open("data/users.json", "w") as f:
            json.dump(users, f)
        # Only perform unwhitelist prompt if user wasn't whitelisted
        if usr["whitelisted"]:
            # Post to staff channel
            channel = client.get_channel(int(settings["request_channel"]))
            e = discord.Embed(title=get_username(usr["uuid"]),
                              description="Unwhitelist request",
                              colour=hc)
            e.set_thumbnail(url="https://crafatar.com/avatars/{}?overlay".format(usr["uuid"]))
            e.add_field(name="Discord User", value=member.mention)
            e.add_field(name="Type", value="Unwhitelist")
            await channel.send(embed=e)


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.message.channel.send("Missing Required Argument: {}.".format(error.param.name))
    elif isinstance(error, commands.BadArgument):
        await ctx.message.channel.send("Bad Argument: Could Not Parse Commands Argument",
                                       embed=discord.Embed(description=repr(error)))
    elif isinstance(error, commands.CommandNotFound):
        def similar(a, b):
            return SequenceMatcher(None, a, b).ratio()

        command = ctx.message.content.split(" ")[0]
        command_similarities = {}
        for cmd in client.commands:
            command_similarities[similar(command, cmd.name)] = cmd.name
        if len(command_similarities) == 0:
            await ctx.message.channel.send("Invalid Command, no similar commands found.")
        highest_command = max([*command_similarities]), command_similarities[max([*command_similarities])]
        if highest_command[0] < 0.55:
            await ctx.message.channel.send("Invalid Command, no commands with greater than 55% similarity found.")
        else:
            await ctx.message.channel.send("Invalid Command, did you mean `{}`?".format(highest_command[1]))
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.message.channel.send(
            "The Command is on Cooldown, Try Again in **{}** seconds".format(str(error.retry_after)),
            embed=discord.Embed(description=repr(error)))
    elif isinstance(error, commands.MissingPermissions):
        await ctx.message.channel.send("Missing Permissions to Run This Command: {}"
                                       .format(", ".join(x.replace("_", " ").title() for x in error.missing_perms)),
                                       embed=discord.Embed(description=repr(error)))
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.message.channel.send("Bot is Missing the Required Permissions to Run This Command: {}"
                                       .format(", ".join(x.replace("_", " ").title() for x in error.missing_perms)),
                                       embed=discord.Embed(description=repr(error)))
    else:
        await ctx.message.channel.send("Uncommon Error <@{}>".format(settings["author_id"]),
                                       embed=discord.Embed(description=repr(error)))


@client.command()
async def help(ctx):
    await ctx.send("""
```md
Whitelist Commands:
- w!whitelist <MC Username> | Add yourself to be whitelisted on the MC server
- w!unwhitelist | Remove yourself from the whitelist system
Admin Commands:
- w!setstatus <User ID/Ping> | Set the whitelist status of a user on the server
- w!adminadd <User ID/Ping> <MC Username> | Forcefully add a user to the whitelist system
- w!export | Export the user JSON file for backups or some other reason
Utility Commands:
- w!playerinfo <MC Username/Discord Ping> | Get info on a MC account
- w!userinfo <User ID/Discord Ping> | Get info on a discord account
- w!avatar <User ID/Discord Ping> | Get a discord account's profile picture
```
""")


@client.command()
async def whitelist(ctx, *, username):
    username = username.strip()  # Remove whitespace, just in case
    # Check if Minecraft username is valid
    if not fullmatch(r"^[a-zA-Z0-9_]{3,16}$", username):
        await ctx.send("That username doesn't seem valid, a minecraft username can only contain the characters "
                       "alphanumerical characters and underscores. They can also only be 3-16 characters long.")
        return
    # Load data
    with open("data/users.json") as f:
        users = json.load(f)
    # Check if user is already whitelisted
    if str(ctx.author.id) in users:
        # Check if whitelist has already been processed
        if users[str(ctx.author.id)]["whitelisted"]:
            await ctx.send("You've already been whitelisted and should be able to connect. If not, contact a staff "
                           "member. If you changed your Minecraft name, you don't need to rewhitelist, if it's an "
                           "entirely new account, run the unwhitelist command then do this again. (Your old account "
                           "will be removed from the whitelist)")
        else:
            await ctx.send("You've already applied to be whitelisted but it hasn't been processed yet, "
                           "please give the staff some time to add you.")
        return
    # Check if the username exists in Mojang servers
    r = requests.get("https://api.mojang.com/users/profiles/minecraft/" + username)
    if r.ok and r.status_code not in [204, 400]:
        js = r.json()
        cuser = js["name"]
        uuid = js["id"]
    else:
        if r.status_code in [204, 400]:
            await ctx.send("I can't seem to find your Minecraft username on Mojang servers, are you using a non-paid MC"
                           "account?")
        else:
            await ctx.send("It seems like the Mojang API is currently broken, try again later?")
        return
    # Set the username's nickname to their MC username
    try:
        await ctx.author.edit(nick=username)
    except discord.errors.Forbidden:
        await ctx.send("Please set your nickname to: " + cuser)
    # Create entry in JSON file
    users[str(ctx.author.id)] = {"uuid": uuid, "whitelisted": False}
    # Write JSON file
    with open("data/users.json", "w") as f:
        json.dump(users, f)
    # Post to staff channel
    channel = client.get_channel(int(settings["request_channel"]))
    e = discord.Embed(title=cuser, description="New whitelist request, when completed, run the setstatus command.",
                      colour=hc)
    e.set_thumbnail(url="https://crafatar.com/avatars/{}?overlay".format(uuid))
    e.add_field(name="Discord User", value=ctx.author.mention)
    e.add_field(name="Type", value="Whitelist")
    await channel.send(embed=e)
    # Notify user of completed application
    await ctx.send("You have been added to the system, a staff member should whitelist you soon.")


@client.command()
async def unwhitelist(ctx):
    # Load data
    with open("data/users.json") as f:
        users = json.load(f)
    # Check if user is not whitelisted
    if str(ctx.author.id) not in users:
        await ctx.send("You're not whitelisted, there's nothing to remove... Did you mean to whitelist yourself?")
    else:
        uuid = users[str(ctx.author.id)]["uuid"]
        del users[str(ctx.author.id)]
        # Write JSON file
        with open("data/users.json", "w") as f:
            json.dump(users, f)
        # Post to staff channel
        channel = client.get_channel(int(settings["request_channel"]))
        e = discord.Embed(title=get_username(uuid), description="Unwhitelist request", colour=hc)
        e.set_thumbnail(url="https://crafatar.com/avatars/{}?overlay".format(uuid))
        e.add_field(name="Discord User", value=ctx.author.mention)
        e.add_field(name="Type", value="Unwhitelist")
        await channel.send(embed=e)
        await ctx.send("You have been removed from the system, a staff member will unwhitelist you shortly.")


@client.command()
@commands.has_permissions(manage_roles=True)
async def setstatus(ctx, user: discord.Member, status: bool):
    # Load data
    with open("data/users.json") as f:
        users = json.load(f)
    # Check if user is not whitelisted
    if str(user.id) not in users:
        await ctx.send("The user is not in the whitelist system. You can ask them to apply or use the adminadd "
                       "command then run this again")
    else:
        users[str(user.id)]["whitelisted"] = status
        # Write JSON file
        with open("data/users.json", "w") as f:
            json.dump(users, f)
        # Attempt to notify user of update
        try:
            await user.send("Your whitelist status has been set to: " + str(status))
        except discord.errors.Forbidden:
            await ctx.send("The whitelist status has been changed and the user has not been notified (DMs disabled)")
        else:
            await ctx.send("The whitelist status has been changed and the user has been notified")


@client.command()
@commands.has_permissions(manage_roles=True)
async def adminadd(ctx, user: discord.Member, *, username):
    username = username.strip()  # Remove whitespace, just in case
    # Check if Minecraft username is valid
    if not fullmatch(r"^[a-zA-Z0-9_]{3,16}$", username):
        await ctx.send("That username doesn't seem valid, a minecraft username can only contain the characters "
                       "alphanumerical characters and underscores. They can also only be 3-16 characters long.")
        return
    # Load data
    with open("data/users.json") as f:
        users = json.load(f)
    # Check if user is already whitelisted
    if str(user.id) in users:
        # Check if whitelist has already been processed
        if users[str(user.id)]["whitelisted"]:
            await ctx.send("They've already been whitelisted and should be able to connect. If not, contact a staff "
                           "member.")
        else:
            await ctx.send("They've already applied to be whitelisted but it hasn't been processed yet.")
        return
    # Check if the username exists in Mojang servers
    r = requests.get("https://api.mojang.com/users/profiles/minecraft/" + username)
    if r.ok and r.status_code not in [204, 400]:
        js = r.json()
        cuser = js["name"]
        uuid = js["id"]
    else:
        if r.status_code in [204, 400]:
            await ctx.send("I can't seem to find that Minecraft username on Mojang servers, is it a non-paid MC"
                           "account?")
        else:
            await ctx.send("It seems like the Mojang API is currently broken, try again later?")
        return
    # Set the username's nickname to their MC username
    try:
        await user.edit(nick=username)
    except discord.errors.Forbidden:
        await ctx.send("Please set their nickname to: " + cuser)
    # Create entry in JSON file
    users[str(user.id)] = {"uuid": uuid, "whitelisted": False}
    # Write JSON file
    with open("data/users.json", "w") as f:
        json.dump(users, f)
    # Post to staff channel
    channel = client.get_channel(int(settings["request_channel"]))
    e = discord.Embed(title=cuser, description="New whitelist request, when completed, run the setstatus command.",
                      colour=hc)
    e.set_thumbnail(url="https://crafatar.com/avatars/{}?overlay".format(uuid))
    e.add_field(name="Discord User", value=user.mention)
    e.add_field(name="Type", value="Whitelist")
    await channel.send(embed=e)
    # Attempt to notify user of update
    try:
        await user.send("You have been forcefully added to the whitelist system by an admin, the username added was: " +
                        cuser)
    except discord.errors.Forbidden:
        await ctx.send("They have been added to the system and the user has not been notified (DMs disabled)")
    else:
        await ctx.send("They have been added to the system and the user has been notified")


@client.command()
async def playerinfo(ctx, player: Union[discord.Member, str]):
    if isinstance(player, discord.Member):
        with open("data/users.json") as f:
            users = json.load(f)
        uuid = users[str(player.id)]["uuid"]
        username = get_username(uuid)
        dscrd = player.mention
    else:
        r = requests.get("https://api.mojang.com/users/profiles/minecraft/" + player)
        if r.ok and r.status_code not in [204, 400]:
            js = r.json()
            username = js["name"]
            uuid = js["id"]
        else:
            if r.status_code in [204, 400]:
                await ctx.send("I can't seem to find that Minecraft user on Mojang servers, is it a non-paid MC"
                               "account?")
            else:
                await ctx.send("It seems like the Mojang API is currently broken, try again later?")
            return
        dscrd = "Unknown"
        # Load data
        with open("data/users.json") as f:
            users = json.load(f)
        for i, j in users.items():
            if uuid == j["uuid"]:
                dscrd = "<@{}>".format(i)
    rhistory = requests.get("https://api.mojang.com/user/profiles/{}/names".format(uuid))
    if rhistory.ok and rhistory.status_code not in [204, 400]:
        history = rhistory.json()
    else:
        if rhistory.status_code in [204, 400]:
            await ctx.send("I can't seem to find that Minecraft user on Mojang servers, is it a non-paid MC"
                           "account?")
        else:
            await ctx.send("It seems like the Mojang API is currently broken, try again later?")
        return
    e = discord.Embed(title=username, description="**Username History:**\n" +
                                                  "\n".join(["- " + i["name"] for i in reversed(history)]), colour=hc)
    e.set_thumbnail(url="https://crafatar.com/avatars/{}?overlay".format(uuid))
    e.set_image(url="https://crafatar.com/renders/body/{}?overlay".format(uuid))
    e.set_footer(text="Thanks to Crafatar for providing the skin renders.")
    e.add_field(name="UUID", value=uuid)
    e.add_field(name="Discord User", value=dscrd)
    await ctx.send(embed=e)


@client.command()
async def userinfo(ctx, *, user: discord.Member):
    embed = discord.Embed(
        description=user.mention,
        colour=hc
    )
    embed.set_thumbnail(url=user.avatar_url)
    embed.set_author(name=user.name + '#' + user.discriminator, icon_url=user.avatar_url)
    embed.add_field(name="Username:", value=user.nick)
    embed.add_field(name="ID:", value=str(user.id))
    embed.add_field(name="Joined At:", value=user.joined_at.strftime("%Y-%m-%d %H:%M:%S.%f UTC"))
    embed.add_field(name="Created At:", value=user.created_at.strftime("%Y-%m-%d %H:%M:%S.%f UTC"))
    embed.add_field(name="Status:", value=user.status)
    embed.add_field(name="Display Colour:", value=f"RGB: {user.colour.to_rgb()}\nHEX: {str(user.colour)}")
    embed.add_field(name="Top Role:", value=user.top_role.name)
    embed.add_field(name="Bot:", value=user.bot)
    embed.add_field(name="System User:", value=user.system)
    roles = []
    for x in user.roles:
        roles.append(x.mention if "everyone" not in x.name else x.name)
    val = ', '.join(x for x in roles)
    if len(val) > 1017:
        wrapper = TextWrapper(width=1017, break_long_words=False, replace_whitespace=False)
        val = wrapper.wrap(val)[0] + "\n**...**"
    embed.add_field(name="Roles:", value=val, inline=False)
    guildperms = user.guild_permissions
    key_perms = {"Administrator": guildperms.administrator, "Ban Members": guildperms.ban_members,
                 "Kick Members": guildperms.kick_members, "Manage Channels": guildperms.manage_channels,
                 "Manage Server": guildperms.manage_guild, "Manage Roles": guildperms.manage_roles,
                 "Manage Nicknames": guildperms.manage_nicknames, "Mute Members": guildperms.mute_members,
                 "Deafen Members": guildperms.deafen_members, "Move Members": guildperms.deafen_members}
    key_permissions = []
    for x, y in key_perms.items():
        if y:
            key_permissions.append(x)
    if len(key_permissions) == 0:
        key_permissions = ["None"]
    key_perm = ", ".join(x for x in key_permissions)
    embed.add_field(name="Key Permissions:", value=key_perm, inline=False)

    await ctx.message.channel.send(embed=embed)


@client.command(aliases=['pfp', 'profile'])
async def avatar(ctx, member: discord.User = None):
    if member is None:
        member = ctx.message.author
    a_embed = discord.Embed(
        description="{}'s Avatar".format(member.mention),
        colour=hc
    )
    a_embed.set_image(url=f'{member.avatar_url}')

    await ctx.message.channel.send(embed=a_embed)


@client.command()
async def bsay(ctx, *, message):
    if str(ctx.author.id) == str(settings["author_id"]):
        await ctx.message.delete()
        await ctx.send(message)


@client.command()
@commands.has_permissions(manage_roles=True)
async def export(ctx):
    with open("data/users.json", "rb") as f:
        try:
            await ctx.send("Here is the user JSON file", file=discord.File(f))
        except discord.errors.InvalidArgument:
            await ctx.send("File is too large too send, ask the hoster for the file instead.")


client.run(BOT_TOKEN)
