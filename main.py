"""
AniList discord bot.
"""

###########
# IMPORTS #
###########

import json
import traceback
import sys
import asyncio
import time
import requests
from discord.ext import commands
import discord
import markdownify
from files import *
from queries import *

#############
# VARIABLES #
#############

COLOR_DEFAULT = discord.Color.teal()
COLOR_ERROR = discord.Color.red()

BOT_VERSION = "1.4.4"


users_glob = {}
users = {}
settings = {}

# How many episodes / chapters are needed for dropped scores
# to enter server score. (0 for no minimum)
MIN_DROP_ANIME = 5
MIN_DROP_MANGA = 25


#############
# FUNCTIONS #
#############


def string_to_hex(color):
    """Converts a color name to color string.

    Keyword arguments:
      color -- Color name.
    """
    if color == "blue":
        return discord.Color.blue()
    if color == "purple":
        return discord.Color.purple()
    if color == "pink":
        return discord.Color.magenta()
    if color == "orange":
        return discord.Color.orange()
    if color == "red":
        return discord.Color.red()
    if color == "green":
        return discord.Color.green()
    if color == "gray":
        return discord.Color.light_gray()
    return COLOR_DEFAULT


def get_user(name):
    """Gets a user from AniList.

    Keyword arguments:
      name -- User's name.
    """
    try:
        # Try to find user by id.
        response = requests.post(
            URL, json={"query": QUERY_USER_ID, "variables": {"id": int(name)}}
        )

        if response.json()["data"]["User"]:
            return response.json()["data"]["User"]
    except:
        pass

    # Find user by name.
    response = requests.post(
        URL, json={"query": QUERY_USER, "variables": {"search": name}}
    )

    if response.json()["data"]["User"]:
        return response.json()["data"]["User"]

    return None


def add_user(guild, id, name, display_name):
    """Adds a user to the user list.

    Keyword arguments:
      id -- User's ID.
      name -- AniList user name.
    """
    user_data = get_user(name)

    if user_data is not None:
        users[str(id)] = {
            "name": user_data["name"],
            "id": user_data["id"],
            "displayName": display_name,
        }

        # Update users
        global users_glob
        users_glob[str(guild)] = users
        update_users(users_glob)
        load_users()

        return True
    return False


def get_media(name, type):
    """Gets a media from AniList.

    Keyword arguments:
      name -- Media name.
      type -- Media type.
    """
    try:
        # Find media by ID.
        response = requests.post(
            URL,
            json={
                "query": QUERY_MEDIA_ID % type.upper(),
                "variables": {"id": int(name)},
            },
        )

        if response.json()["data"]["Media"] is not None:
            return response.json()["data"]["Media"]
    except:
        pass

    # Find media by name.
    response = requests.post(
        URL, json={"query": QUERY_MEDIA %
                   type.upper(), "variables": {"search": name}}
    )

    if response.json()["data"]["Media"] is not None:
        return response.json()["data"]["Media"]

    return None


def get_character(name):
    """Gets a character from AniList.

    Keyword arguments:
      name -- Character name.
    """
    try:
        # Find character by ID.
        response = requests.post(
            URL, json={"query": QUERY_CHARACTER_ID, "variables": {"id": int(name)}}
        )

        if response.json()["data"]["Character"] is not None:
            return response.json()["data"]["Character"]
    except:
        pass

    # Find character by name.
    response = requests.post(
        URL, json={"query": QUERY_CHARACTER, "variables": {"search": name}}
    )

    if response.json()["data"]["Character"] is not None:
        return response.json()["data"]["Character"]

    return None


def search_media(name, media_type=None):
    """Searches a media on AniList.

    Keyword arguments:
      name -- Search query.
      media_type -- Media type.
    """
    variables = {
        "search": name,
        "page": 1,
        "perPage": 25,
    }
    if media_type is not None:
        response = requests.post(
            URL,
            json={
                "query": QUERY_SEARCH_MEDIA_TYPE % media_type.upper(),
                "variables": variables,
            },
        )
    else:
        response = requests.post(
            URL, json={"query": QUERY_SEARCH_MEDIA, "variables": variables}
        )

    return response.json()["data"]["Page"]


def search_character(name):
    """Searches a character on AniList.

    Keyword arguments:
      name -- Search query.
    """
    variables = {
        "search": name,
        "page": 1,
        "perPage": 25,
    }

    response = requests.post(
        URL, json={"query": QUERY_SEARCH_CHARACTER, "variables": variables}
    )

    return response.json()["data"]["Page"]


def search_user(name):
    """Searches a user on AniList.

    Keyword arguments:
      name -- Search query.
    """
    variables = {
        "search": name,
        "page": 1,
        "perPage": 25,
    }

    response = requests.post(
        URL, json={"query": QUERY_SEARCH_USER, "variables": variables}
    )

    return response.json()["data"]["Page"]


def get_user_score(userId, mediaId, repeat=0):
    """Gets a user score on a specific media.

    Keyword arguments:
      userId -- User ID.
      mediaId -- Media ID.
    """
    variables = {"userId": userId, "mediaId": mediaId}
    response = requests.post(
        URL, json={"query": QUERY_MEDIALIST, "variables": variables}
    )

    try:
        return response.json()["data"]["MediaList"]
    except:
        print(response.text)
        print(f"Error - {userId}\n{response.text}")
        if repeat <= 5:
            time.sleep(1)
            # TODO: better solution
            return get_user_score(userId, mediaId, repeat + 1)
        else:
            return None


def get_seasonal(season, year, page, perPage):
    variables = {"year": year, "page": page, "perPage": perPage}

    response = requests.post(
        URL, json={"query": QUERY_SEASONAL % season, "variables": variables}
    )

    return response.json()["data"]["Page"]


def get_users_statuses(loc_users, mediaId, media_type):
    """Gets the statuses / scores of all the connected users on a specific media.

    Keyword arguments:
    mediaId -- Media ID.
    """
    # FIXME: Find a way to speed up queries.
    result = {}

    query = """
query ($mediaId: Int) {
    %s
}"""
    media_query = """
    %s: MediaList(userId: %s, mediaId: $mediaId) {
        status,
        score (format: POINT_100),
        progress,
    },"""
    media_query_combined = ""

    for user in loc_users:
        value = loc_users[user]
        media_query_combined += media_query % ("_" + value["name"], str(value["id"]))

    query = query % media_query_combined
    # print(query)

    variables = {"mediaId": mediaId}
    response = requests.post(URL, json={"query": query, "variables": variables})
    # print(response.text)

    average_score = 0
    scores = 0
    for user in loc_users:
        value = loc_users[user]
        score = get_user_score(value["id"], mediaId)
        # time.sleep(0.001)
        if score is not None:
            if score["score"] == 0:
                score["score"] = "?"

            if score["status"] == "COMPLETED":
                status = f'{value["displayName"]} **({score["score"]})**'
                if score["score"] != "?":
                    average_score += score["score"]
                    scores += 1
            elif score["status"] == "CURRENT":
                status = f'{value["displayName"]} [{score["progress"]}] **({score["score"]})**'
                if score["score"] != "?":
                    average_score += score["score"]
                    scores += 1
            elif score["status"] == "REPEATING":
                status = f'{value["displayName"]} [{score["progress"]}/__R__] **({score["score"]})**'
                if score["score"] != "?":
                    average_score += score["score"]
                    scores += 1
            elif score["status"] == "PAUSED":
                status = f'{value["displayName"]} [{score["progress"]}/__P__] **({score["score"]})**'
                if score["score"] != "?":
                    average_score += score["score"]
                    scores += 1
            elif score["status"] == "DROPPED":
                status = f'{value["displayName"]} [{score["progress"]}] **({score["score"]})**'
                if (media_type == "ANIME" and score["progress"] >= MIN_DROP_ANIME) or (
                    media_type == "MANGA" and score["progress"] >= MIN_DROP_MANGA
                ):
                    if score["score"] != "?":
                        average_score += score["score"]
                        scores += 1
            else:
                status = value["displayName"]

            if score["status"] == "REPEATING":
                score["status"] = "CURRENT"
            if score["status"] == "PAUSED":
                score["status"] = "CURRENT"

            if score["status"] in result:
                result[score["status"]].append(status)
            else:
                result[score["status"]] = [status]
        else:
            if "NOT ON LIST" in result:
                result["NOT ON LIST"].append(value["displayName"])
            else:
                result["NOT ON LIST"] = [value["displayName"]]

    result_sort = {}

    if average_score != 0:
        average_score /= scores
        result_sort["AVERAGE"] = average_score

    if "COMPLETED" in result:
        result_sort["COMPLETED"] = result["COMPLETED"]
    if "CURRENT" in result:
        result_sort["CURRENT"] = result["CURRENT"]
    if "DROPPED" in result:
        result_sort["DROPPED"] = result["DROPPED"]
    if "PLANNING" in result:
        result_sort["PLANNING"] = result["PLANNING"]
    if "NOT ON LIST" in result:
        result_sort["NOT ON LIST"] = result["NOT ON LIST"]
    return result_sort


def bot_get_media(media_type, name):
    """Gets a media from AniList and generates an embedded message.

    Keyword arguments:
      media_type -- Media type.
      name -- Media name.
    """
    media = get_media(name, media_type)
    if media is None:
        embed = discord.Embed(title="Not Found", description="):", color=COLOR_DEFAULT)
    else:
        # user_scores = get_users_statuses(media["id"], media["type"])

        if media["season"] is not None:
            media["season"] = f'{media["season"].capitalize()} {media["seasonYear"]}'

        # Replace 'None' with '?'
        for i in media:
            if media[i] is None:
                media[i] = "?"

        if media["title"]["english"] is None:
            media["title"]["english"] = media["title"]["romaji"]

        if not media["genres"]:
            media["genres"] = ["?"]

        # Shorten description
        if len(media["description"]) >= 1024:
            media["description"] = media["description"][:1020] + "..."
        media["description"] = markdownify.markdownify(media["description"])
        media["description"] = media["description"].split(" ", 65)[0:65]
        description = " ".join(media["description"]) + "..."

        embed = discord.Embed(
            title=media["title"]["english"],
            url=media["siteUrl"],
            description=f'{media["title"]["native"]} - '
            + f'{media["title"]["romaji"]}\n\n',
            color=COLOR_DEFAULT,
        )
        embed.set_thumbnail(url=media["coverImage"]["extraLarge"])
        if media["bannerImage"] != "?":
            embed.set_image(url=media["bannerImage"])
        embed.add_field(name="Mean Score", value=media["meanScore"])
        embed.add_field(name="Type", value=media["type"].capitalize())
        embed.add_field(
            name="Status", value=media["status"].capitalize().replace("_", " ")
        )
        embed.add_field(name="Season", value=media["season"])
        embed.add_field(name="Popularity", value=media["popularity"])
        embed.add_field(name="Favourited", value=f'{media["favourites"]} times')
        if media_type.lower() == "anime":
            embed.add_field(name="Episodes", value=media["episodes"])
            embed.add_field(
                name="Duration", value=f'{media["duration"]} minutes per episode'
            )
        else:
            embed.add_field(name="Chapters", value=media["chapters"])
            embed.add_field(name="Volumes", value=media["volumes"])
        embed.add_field(name="Format", value=media["format"])
        embed.add_field(name="Genres", value=" - ".join(media["genres"]), inline=False)
        embed.add_field(name="Description", value=description, inline=False)

        # # embed.add_field(name="User Scores", value=" ")
        # for status in user_scores:
        #     embed.add_field(
        #         name=status, value=" | ".join(user_scores[status]), inline=False
        #     )
    return embed


############
# COMMANDS #
############


# Settings
settings = load_settings()
prefix = settings["prefix"]
print(settings)

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix=prefix, help_command=None, case_insensitive=True, intents=intents
)


@bot.event
async def on_ready():
    """Gets called when the bot goes online."""
    print("We have logged in as {0.user}".format(bot))
    for guild in bot.guilds:
        print(guild.id, "-", guild.name)

    global users_glob
    users_glob = load_users()
    print(users_glob)


@bot.event
async def on_message(message):
    global users, users_glob

    if not validate_users(users_glob):
        print("sadasd")
        users_glob = load_users()  # Hope this works. TODO: Something better

    if str(message.channel.guild.id) not in users_glob:
        users_glob[str(message.channel.guild.id)] = {}
        update_users(users_glob)
    if str(message.channel.guild.id) not in settings["servers"]:
        if settings["servers"]:
            settings["servers"][str(message.guild.id)] = {"channels": None}
        else:
            settings["servers"] = {str(message.guild.id): {"channels": None}}
        update_settings(settings)

    users = users_glob[str(message.channel.guild.id)]
    channels = settings["servers"][str(message.guild.id)]["channels"]

    if channels is None or channels == [] or str(message.channel.id) in channels:
        await bot.process_commands(message)


@bot.command(
    name="help", description="Displays this message.", help=prefix + "help (command)"
)
async def help(ctx, help_command=""):
    """Shows help.

    Keyword arguments:
      ctx -- context.
      help_command -- Command to show help of.
    """

    help_text = {}

    if help_command == "":
        embed = discord.Embed(title="Help", color=COLOR_DEFAULT)
        categories = []
        for command in bot.commands:
            if command.cog.__class__.__name__ not in categories:
                categories.append(command.cog.__class__.__name__)

        for category in categories:
            help_text[category] = ""
            for command in bot.commands:
                if command.cog.__class__.__name__ == category:
                    help_text[category] += f"`{command}` - {command.description}\n"

        for category in categories:
            if category == "NoneType":
                embed.add_field(
                    name="Commands", value=help_text[category], inline=False
                )
            else:
                embed.add_field(name=category, value=help_text[category], inline=False)

        help_text = f"\n**Prefix:** `{prefix}`"
        help_text += f"\nUse `{prefix}help [command]` to get more info on the command."
        help_text += f"\n**Version:** {BOT_VERSION}"
        embed.add_field(name="Info", value=help_text, inline=False)
    else:
        is_command = False
        for command in bot.commands:
            if command.name == help_command:
                embed = discord.Embed(
                    title=command.name,
                    description=command.description,
                    color=COLOR_DEFAULT,
                )
                embed.add_field(
                    name="Usage", value=f"```{command.help}```", inline=False
                )
                if command.aliases:
                    embed.add_field(
                        name="Aliases",
                        value=f"`{'` | `'.join(command.aliases)}`",
                        inline=False,
                    )
                is_command = True
                break

        if not is_command:
            embed = discord.Embed(
                title=help_command,
                description=f"`{help_command}` is not a command.",
                color=COLOR_ERROR,
            )

    await ctx.send(embed=embed)


@bot.command(name="ping", description="Pong!", help=prefix + "ping")
async def ping(ctx):
    """Shows bot latency.

    Keyword arguments:
      ctx -- Context.
    """

    await ctx.send("Pong!\n{:d} ms".format(int(round(bot.latency, 3) * 1000)))


@bot.command(
    name="set-channels",
    description="_[ADMIN]_ Sets bot's command channels",
    help=prefix + "set-channels [channels]",
)
async def set_channels(ctx, *channels):
    if not ctx.message.author.guild_permissions.administrator:
        return

    channels_id = []

    for channel in channels:
        channel = channel.strip("<#>")
        exists = False
        for g_channel in ctx.guild.channels:  # TODO: better method
            try:
                if g_channel.id == int(channel):
                    exists = True
            except:
                pass
        if not exists:
            await ctx.send(f"Channel {channel} does not exist, skipping.")
            continue
        channels_id.append(channel)

    settings["servers"][str(ctx.guild.id)]["channels"] = channels_id
    update_settings(settings)

    await ctx.send("Channels set successfully!")


@bot.command(
    name="anime",
    description="Search for a specific anime using its name.",
    help=prefix + "anime [name]",
)
async def anime(ctx, *name):
    """Shows an anime from AniList.

    Keyword arguments:
      ctx -- Context.
      *name -- Anime name.
    """

    if not name:
        embed = discord.Embed(
            title="Incorrect usage",
            description=f"Usage: `{prefix}anime [name]`",
            color=COLOR_ERROR,
        )
    else:
        embed = bot_get_media("anime", " ".join(name))
    await ctx.send(embed=embed)


@bot.command(
    name="manga",
    description="Search for a specific manga using its name.",
    help=prefix + "manga [name]",
)
async def manga(ctx, *name):
    """Shows a manga from AniList.

    Keyword arguments:
      ctx -- Context
      *name -- Manga name.
    """

    if not name:
        embed = discord.Embed(
            title="Incorrect usage",
            description=f"Usage: `{prefix}manga [name]`",
            color=COLOR_ERROR,
        )
    else:
        embed = bot_get_media("manga", " ".join(name))
    await ctx.send(embed=embed)


@bot.command(
    name="user",
    description="Search for a specific username.",
    help=prefix + "user <user|mention>",
)
async def user(ctx, name=None):
    """Shows a user from AniList.

    Keyword arguments:
      ctx -- Context.
      name -- User's name.
    """

    try:
        name = users[name.strip("<@!>")]["name"]
    except:
        pass

    if name is None:
        name = users[str(ctx.message.author.id)]["name"]

    user_data = get_user(name)

    if user_data is not None:

        embed = discord.Embed(
            title=user_data["name"] + " - AniList Statistics",
            url=user_data["siteUrl"],
            color=string_to_hex(user_data["options"]["profileColor"]),
        )
        embed.set_thumbnail(url=user_data["avatar"]["large"])
        if user_data["bannerImage"] is not None:
            embed.set_image(url=user_data["bannerImage"])
        if user_data["about"] is not None:
            if len(user_data["about"]) >= 1024:
                user_data["about"] = user_data["about"][:1020] + "..."
            # embed.add_field(name="About", value=user_data["about"])

        stats_anime = user_data["statistics"]["anime"]
        if stats_anime["formats"] != []:
            stats_anime["format"] = stats_anime["formats"][0]["format"]
        else:
            stats_anime["format"] = "Unknown"
        if stats_anime["genres"] != []:
            genres = []
            for i in stats_anime["genres"]:
                genres.append(i["genre"])
            stats_anime["genres"] = " / ".join(genres)
        else:
            stats_anime["genres"] = "Unknown"

        time = int(stats_anime["minutesWatched"])
        days = time // 1440
        leftover_minutes = time % 1440
        hours = leftover_minutes // 60
        mins = time - (days * 1440) - (hours * 60)

        anime_stats_str = (
            f'- Total Entries: **{stats_anime["count"]}**\n'
            + f'- Mean Score: **{stats_anime["meanScore"]}**\n'
            + f'- Episodes Watched: **{stats_anime["episodesWatched"]}**\n'
            + f"- Time Watched: **{days} days, {hours} hours and {mins} minutes**\n"
            + f'- Favorite Format: **{stats_anime["format"]}**\n'
            + f'- Favorite Genres: **{stats_anime["genres"]}**\n'
        )
        stats_manga = user_data["statistics"]["manga"]
        if stats_manga["formats"] != []:
            stats_manga["format"] = stats_manga["formats"][0]["format"]
        else:
            stats_manga["format"] = "Unknown"
        if stats_manga["genres"] != []:
            genres = []
            for i in stats_manga["genres"]:
                genres.append(i["genre"])
            stats_manga["genres"] = " / ".join(genres)
        else:
            stats_manga["genres"] = "Unknown"
        manga_stats_str = (
            f'- Total Entries: **{stats_manga["count"]}**\n'
            + f'- Mean Score: **{stats_manga["meanScore"]}**\n'
            + f'- Volumes Read: **{stats_manga["volumesRead"]}**\n'
            + f'- Chapters Read: **{stats_manga["chaptersRead"]}**\n'
            + f'- Favorite Format: **{stats_manga["format"]}**\n'
            + f'- Favorite Genres: **{stats_manga["genres"]}**\n'
        )

        embed.add_field(name="Anime Statistics", value=anime_stats_str, inline=False)
        embed.add_field(name="Manga Statistics", value=manga_stats_str, inline=False)
    else:
        embed = discord.Embed(title="Not Found", description="):", color=COLOR_DEFAULT)

    await ctx.send(embed=embed)


@bot.command(
    name="link",
    description="Links your discord account to an AniList user.",
    help=prefix + "link [name]",
)
async def link(ctx, name=None):
    """Links a user to AniList account.

    Keyword arguments:
      ctx -- Context.
      name -- AniList user's name.
    """

    if name is None:
        embed = discord.Embed(
            title="Incorrect usage",
            description=f"Usage: `{prefix}link [name]`",
            color=COLOR_ERROR,
        )
        await ctx.send(embed=embed)
        return

    found_user = get_user(name)
    for _user in users:
        if users[_user]["name"] == found_user["name"]:
            await ctx.send("User taken.")
            return

    if add_user(
        ctx.message.guild.id, ctx.message.author.id, name, ctx.message.author.name
    ):
        await user(ctx, name)
        await ctx.send("Linked successfully")
    else:
        await ctx.channel.send("Not Found")


@bot.command(
    name="unlink",
    description="Removes the link between your discord account and an AniList user.",
    help=prefix + "unlink",
)
async def unlink(ctx):
    """Unlinks a user from linked AniList account.

    Keyword arguments:
      ctx -- Context.
    """

    global users_glob
    del users[str(ctx.message.author.id)]
    users_glob[(ctx.message.channel.guild.id)] = users

    # Update users
    update_users(users_glob)
    load_users()

    embed = discord.Embed(
        title="User unlinked successfully", description="Hurrah!", color=COLOR_DEFAULT
    )
    await ctx.send(embed=embed)


@bot.command(
    name="users", description="Shows all users currently linked.", help=prefix + "users"
)
async def show_users(ctx):
    """Show all connected users.

    Keyword arguments:
      ctx -- Context.
    """

    result = []
    for i in users:
        result.append(
            f'**Discord:** {users[i]["displayName"]} - **AniList:** [{users[i]["name"]}](https://AniList.co/user/{users[i]["id"]})'
        )

    # Split users
    s = []
    for i in range(0, int(len(result)) + 1, 20):
        c = result[i : i + 20]
        if c != []:
            s.append(c)
    result = []

    for i in s:
        result.append("\n".join(i))

    embed = discord.Embed(
        title=f"Total linked users: {len(users)}",
        description=f"{result[0]}",
        color=COLOR_DEFAULT,
    )
    message = await ctx.send(embed=embed)

    pages = len(result)
    cur_page = 1

    await message.add_reaction("◀️")
    await message.add_reaction("▶️")

    def check(reaction, user):
        # This makes sure nobody except the command sender can interact with the "menu"
        return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"]

    while True:
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60, check=check)
            # waiting for a reaction to be added - times out after 60 seconds

            if str(reaction.emoji) == "▶️" and cur_page != pages:
                # Go to next page
                cur_page += 1
                embed = discord.Embed(
                    title=f"Total linked users: {len(users)}",
                    description=f"{result[cur_page - 1]}",
                    color=COLOR_DEFAULT,
                )
                await message.edit(embed=embed)
                await message.remove_reaction(reaction, user)

            elif str(reaction.emoji) == "◀️" and cur_page > 1:
                # Go to previous page
                cur_page -= 1
                embed = discord.Embed(
                    title=f"Total linked users: {len(users)}",
                    description=f"{result[cur_page - 1]}",
                    color=COLOR_DEFAULT,
                )
                await message.edit(embed=embed)
                await message.remove_reaction(reaction, user)

            else:
                # removes reactions if the user tries to go forward on the last page or
                # backwards on the first page
                await message.remove_reaction(reaction, user)
        except asyncio.TimeoutError:
            # ending the loop if user doesn't react after x seconds
            break


@bot.command(
    name="top",
    description="Shows the top medias of a user.",
    help=prefix + "top [top_count] <name|mention>",
)
async def top(ctx, top_count=10, name=None):
    """Shows a user's top media.

    Keyword arguments:
      ctx -- Context.
      name -- User's name.
    """

    try:
        name = users[name.strip("<@!>")]["name"]
    except:
        pass

    if name is None:
        try:
            name = users[str(ctx.message.author.id)]["name"]
        except:
            name = " "

    user_data = get_user(name)
    if user_data is not None:
        variables = {"userId": user_data["id"], "page": 1, "perPage": top_count}

        response = requests.post(
            URL, json={"query": QUERY_TOP_MEDIA, "variables": variables}
        )
        media_list = response.json()["data"]["Page"]["mediaList"]

        description = ""
        for media in media_list:
            if media["media"]["title"]["english"] is None:
                media["media"]["title"]["english"] = media["media"]["title"]["romaji"]
            description += (
                f'{media["media"]["title"]["english"]} *[{media["media"]["type"]}]* - '
                + f'**{media["score"]}**\n'
            )

        embed = discord.Embed(
            title=f"{name}'s top {top_count}",
            description=description,
            color=string_to_hex(user_data["options"]["profileColor"]),
        )
        embed.set_thumbnail(url=user_data["avatar"]["large"])
    else:
        embed = discord.Embed(title="Not Found", description="):", color=COLOR_DEFAULT)

    await ctx.send(embed=embed)


@bot.command(
    name="search",
    description="Search for specific information. shows all results.",
    help=prefix + "search [media|anime|manga|character|user] [name]",
)
async def search(ctx, search_type=None, *search_string):
    """Searches for media/character/user on AniList.

    Keyword arguments:
      ctx -- Context.
      search_type -- Search type.
      *search_string -- Search query.
    """

    search_string = " ".join(search_string)

    result = ""
    if search_type is None or not search_string:
        result = "Usage: 'search [anime|manga|character|media|user] [name]'"

    elif search_type.lower() in ("media", "anime", "manga"):
        if search_type.lower() == "media":
            medias = search_media(search_string)
        elif search_type.lower() in ("anime", "manga"):
            medias = search_media(search_string, search_type)

        for media in medias["media"]:
            result += f'{media["type"].capitalize()} {media["id"]} - '

            if media["title"]["english"] is not None:
                title = media["title"]["english"]
            elif media["title"]["romaji"] is not None:
                title = media["title"]["romaji"]
            else:
                title = media["title"]["native"]

            if len(title) > 70:
                title = title[:67] + "..."

            result += title
            result += "\n"
    elif search_type.lower() == "character":
        characters = search_character(search_string)

        for character in characters["characters"]:
            result += f'Character {character["id"]} - '

            if character["name"]["full"] is not None:
                result += character["name"]["full"]
            else:
                result += character["name"]["native"]

            result += "\n"
    elif search_type.lower() == "user":
        found_users = search_user(search_string)

        for user in found_users["users"]:
            result += f'User {user["id"]} - {user["name"]}\n'
    else:
        result = "Usage: 'search [anime|manga|character|media|user] [name]'"

    if result == "":
        result = "No results ):"

    await ctx.send(f"```{result}```")


@bot.command(
    name="score",
    description="Shows a user's score for a specific media.",
    help=prefix + "score [user|mention] [name]",
)
async def score(ctx, name, *media_name):
    """Shows a user score/status for a specific media.

    Keyword arguments:
      ctx -- Context.
      name -- User's name.
      *media_name -- Media name.
    """

    media_name = " ".join(media_name)

    try:
        name = users[name.strip("<@!>")]["name"]
    except:
        pass

    user_data = get_user(name)
    media = get_media(media_name, "anime")
    media_manga = get_media(media_name, "manga")

    if media is None:
        media = media_manga

    if user_data is not None and media is not None:
        score = get_user_score(user_data["id"], media["id"])
        if score is None:
            score = get_user_score(user_data["id"], media_manga["id"])
            media = media_manga
        if media["title"]["english"] is None:
            media["title"]["english"] = media["title"]["romaji"]
        if score is not None:
            embed = discord.Embed(
                title=f'{user_data["name"]}\'s score for {media["title"]["english"]}',
                color=string_to_hex(user_data["options"]["profileColor"]),
            )
            if score["status"] == "COMPLETED":
                embed.add_field(name="Score", value=score["score"])
                embed.add_field(name="Notes", value=score["notes"])
            else:
                if score["status"] == "CURRENT":
                    score["status"] = (
                        "Watching" if media["type"] == "ANIME" else "Reading"
                    )
                embed.add_field(name="Status", value=score["status"].capitalize())
                embed.add_field(name="Progress", value=score["progress"])
            embed.set_thumbnail(url=user_data["avatar"]["large"])
        else:
            embed = discord.Embed(
                title="Not found.", description="):", color=COLOR_DEFAULT
            )
    else:
        embed = discord.Embed(title="Not found.", description="):", color=COLOR_DEFAULT)
    await ctx.send(embed=embed)


@bot.command(
    name="scores",
    description="Gets user scores for a specific media",
    help=prefix + "scores [anime|manga] [name]",
)
async def scores(ctx, media_type=None, *name):
    """Shows linked users scores for a specific media.

    Keyword arguments:
      ctx -- Context.
      media_type -- Media type.
      *name -- Media name.
    """

    await ctx.send("This might take some time...")

    if media_type is None or not name:
        embed = discord.Embed(
            title="Incorrect usage",
            description=f"Usage: `{prefix}scores [anime|manga] [name]`",
            color=COLOR_ERROR,
        )
        await ctx.send(embed=embed)
        return

    if media_type.lower() == "anime":
        media = get_media(" ".join(name), "anime")
    elif media_type.lower() == "manga":
        media = get_media(" ".join(name), "manga")
    else:
        embed = discord.Embed(
            title="Incorrect usage",
            description=f"Usage: `{prefix}scores [anime|manga] [name]`",
            color=COLOR_ERROR,
        )
        await ctx.send(embed=embed)
        return

    if media is not None:
        loc_users = users_glob[str(ctx.message.guild.id)]
        user_scores = get_users_statuses(loc_users, media["id"], media["type"])

        if media["title"]["english"] is None:
            media["title"]["english"] = media["title"]["romaji"]

        embed = discord.Embed(
            title=f'User scores for {media["title"]["english"]}', color=COLOR_DEFAULT
        )
        for status in user_scores:
            if status == "AVERAGE":
                embed.add_field(
                    name="SERVER SCORE",
                    value=str(int(user_scores[status])),
                )
                embed.add_field(
                    name="AniList SCORE",
                    value=media["meanScore"],
                )
            else:
                embed.add_field(
                    name=status, value=" | ".join(user_scores[status]), inline=False
                )
        embed.set_thumbnail(url=media["coverImage"]["extraLarge"])
        embed.set_footer(
            text=f'Dropped scores affect server score only if progress is {MIN_DROP_ANIME if media["type"] == "ANIME" else MIN_DROP_MANGA} or more.'
        )
    else:
        embed = discord.Embed(title="Not found.", description="):", color=COLOR_ERROR)

    await ctx.send(embed=embed)


@bot.command(
    name="character",
    description="Search for a specific character using its name.",
    help=prefix + "character [name]",
)
async def show_character(ctx, *name):
    """Shows a character from AniList.

    Keyword arguments:
      ctx -- Context.
      *name -- Character's name.
    """

    character = get_character(" ".join(name))

    if character is not None:
        if len(character["description"]) >= 1024:
            character["description"] = character["description"][:1020] + "..."
        character["description"] = character["description"].replace("~!", "||")
        character["description"] = character["description"].replace("!~", "||")
        character["name"]["alternative"].append(character["name"]["native"])

        embed = discord.Embed(
            title=character["name"]["full"],
            description=character["description"],
            url=character["siteUrl"],
            color=COLOR_DEFAULT,
        )
        embed.set_thumbnail(url=character["image"]["large"])
        relations = " "
        for i in character["media"]["edges"]:
            if i["node"]["title"]["english"] is not None:
                relation = f'• [{i["node"]["title"]["english"]}]({i["node"]["siteUrl"]}) [{i["characterRole"].capitalize()}]\n'
            else:
                relation = f'• [{i["node"]["title"]["native"]}]({i["node"]["siteUrl"]}) [{i["characterRole"].capitalize()}]\n'

            if len(relations) + len(relation) >= 1024:
                break

            relations += relation

        embed.add_field(name="Relations", value=relations, inline=False)
        embed.add_field(
            name="Aliases",
            value=" - ".join(character["name"]["alternative"]),
            inline=False,
        )
        embed.add_field(name="AniList ID", value=character["id"])
        embed.add_field(name="Favourites", value=character["favourites"])
    else:
        embed = discord.Embed(
            title="Incorrect usage",
            description=f"Usage: `{prefix}character [name]`",
            color=COLOR_ERROR,
        )

    await ctx.send(embed=embed)


# @bot.command(
#     name="affinity",
#     description="TBD",
#     help=prefix + "affinity [name|mention] [name|mention]",
# )
# async def affinity(ctx, user1, user2):  # TODO

#     try:
#         user1 = users[user1.strip("<@!>")]["name"]
#     except:
#         pass
#     try:
#         user2 = users[user2.strip("<@!>")]["name"]
#     except:
#         pass

#     user1_data = get_user(user1)
#     user2_data = get_user(user2)

#     if user1_data is not None and user2_data is not None:
#         variables1 = {"userId": user1_data["id"], "page": 1, "perPage": 50}
#         variables2 = {"userId": user2_data["id"], "page": 1, "perPage": 50}

#         response = requests.post(
#             URL, json={"query": QUERY_TOP_MEDIA, "variables": variables1}
#         )
#         media_list1 = response.json()["data"]["Page"]["mediaList"]
#         response = requests.post(
#             URL, json={"query": QUERY_TOP_MEDIA, "variables": variables2}
#         )
#         media_list2 = response.json()["data"]["Page"]["mediaList"]

#         # print(media_list1)
#         # print(media_list2)

#         medias1 = medias2 = []
#         for i in media_list1:
#             medias1.append(i["media"])
#         for i in media_list2:
#             medias2.append(i["media"])

#         for i in medias1:
#             if i in medias2:
#                 print(i, ":", i in medias1 and i in medias2)


@bot.command(
    name="favourites",
    description="Shows a user's favourites.",
    help=prefix + "favourites [name|mention]",
    aliases=["favorites"],
)
async def favorites(ctx, name=None):  # TODO: errors
    """Shows a user's favourites.

    Keyword arguments:
      ctx -- Context.
      name -- User's name.
    """

    try:
        name = users[name.strip("<@!>")]["id"]
    except:
        pass

    if name is None:
        try:
            name = users[str(ctx.message.author.id)]["id"]
        except:
            name = " "

    user = get_user(name)
    if user is not None:
        embed = discord.Embed(
            title=user["name"] + "'s favourites",
            color=string_to_hex(user["options"]["profileColor"]),
        )

        # Create embed strings
        anime = ""
        manga = ""
        characters = ""
        staff = ""
        studios = ""
        for node in user["favourites"]["anime"]["edges"]:
            media = node["node"]

            if media["title"]["english"] is None:
                media["title"]["english"] = media["title"]["romaji"]
            anime += f'• [{media["title"]["english"]}]({media["siteUrl"]}) *({media["id"]})*\n'

        for node in user["favourites"]["manga"]["edges"]:
            media = node["node"]

            if media["title"]["english"] is None:
                media["title"]["english"] = media["title"]["romaji"]
            manga += f'• [{media["title"]["english"]}]({media["siteUrl"]}) *({media["id"]})*\n'
        for node in user["favourites"]["characters"]["edges"]:
            media = node["node"]

            if media["name"]["full"] is None:
                media["name"]["full"] = media["name"]["native"]
            characters += (
                f'• [{media["name"]["full"]}]({media["siteUrl"]}) *({media["id"]})*\n'
            )
        for node in user["favourites"]["staff"]["edges"]:
            media = node["node"]

            if media["name"]["full"] is None:
                media["name"]["full"] = media["name"]["native"]
            staff += (
                f'• [{media["name"]["full"]}]({media["siteUrl"]}) *({media["id"]})*\n'
            )
        for node in user["favourites"]["studios"]["edges"]:
            media = node["node"]

            studios += f'• [{media["name"]}]({media["siteUrl"]}) *({media["id"]})*\n'

        # Add fields if strings are not empty
        if anime != "":
            embed.add_field(name="Anime", value=anime, inline=False)
        if manga != "":
            embed.add_field(name="Mangas", value=manga, inline=False)
        if characters != "":
            embed.add_field(name="Characters", value=characters, inline=False)
        if staff != "":
            embed.add_field(name="Staff", value=staff, inline=False)
        if studios != "":
            embed.add_field(name="Studios", value=studios, inline=False)
    else:
        embed = discord.Embed(title="Not Found", description="):", color=COLOR_DEFAULT)

    await ctx.send(embed=embed)


@bot.command(
    name="seasonal",
    description="Shows seasonal anime.",
    help=prefix + "seasonal [season] [year]",
    aliases=["season"],
)
async def seasonal(ctx, season=None, year=None):
    if season is None or year is None:
        embed = discord.Embed(
            title="Incorrect usage",
            description=f"Usage: `{prefix}seasonal [season] [year]`",
            color=COLOR_ERROR,
        )
        await ctx.send(embed=embed)
        return

    if season.upper() not in ("FALL", "WINTER", "SPRING", "SUMMER"):
        embed = discord.Embed(
            title="Invalid season",
            description="Valid seasons are: `WINTER|SPRING|SUMMER|FALL`",
            color=COLOR_ERROR,
        )
        await ctx.send(embed=embed)
        return

    medias = get_seasonal(season.upper(), year, 1, 25)

    result = "```Page 1\nID     - Name\n"
    for media in medias["media"]:
        if media["title"]["english"] is None:
            media["title"]["english"] = media["title"]["romaji"]
        result += f'{media["id"]} - {media["title"]["english"]}\n'
    result += "```"
    message = await ctx.send(result)

    cur_page = 1

    await message.add_reaction("◀️")
    await message.add_reaction("▶️")

    def check(reaction, user):
        # This makes sure nobody except the command sender can interact with the "menu"
        return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"]

    while True:
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60, check=check)
            # waiting for a reaction to be added - times out after 60 seconds

            if str(reaction.emoji) == "▶️":  # and cur_page != pages:
                # Go to next page
                cur_page += 1
                medias = get_seasonal(season.upper(), year, cur_page, 25)
                if not medias["media"]:
                    cur_page -= 1
                    await message.remove_reaction(reaction, user)
                    continue
                result = f"```Page {cur_page}\nID     - Name\n"
                for media in medias["media"]:
                    if media["title"]["english"] is None:
                        media["title"]["english"] = media["title"]["romaji"]
                    result += f'{media["id"]} - {media["title"]["english"]}\n'
                result += "```"
                await message.edit(content=result)
                await message.remove_reaction(reaction, user)
            elif str(reaction.emoji) == "◀️" and cur_page > 1:
                # Go to previous page
                cur_page -= 1
                medias = get_seasonal(season.upper(), year, cur_page, 25)
                result = f"```Page {cur_page}\nID     - Name\n"
                for media in medias["media"]:
                    if media["title"]["english"] is None:
                        media["title"]["english"] = media["title"]["romaji"]
                    result += f'{media["id"]} - {media["title"]["english"]}\n'
                result += "```"
                await message.edit(content=result)
                await message.remove_reaction(reaction, user)
            else:
                # removes reactions if the user tries to go forward on the last page or
                # backwards on the first page
                await message.remove_reaction(reaction, user)
        except asyncio.TimeoutError:
            # ending the loop if user doesn't react after x seconds
            break


@bot.event
async def on_member_remove(member):
    # Update users
    global users_glob
    del users[str(member.id)]
    users_glob[(member.guild.id)] = users

    update_users(users_glob)
    load_users()


@bot.event
async def on_command_error(ctx, error):
    await ctx.message.add_reaction("❓")
    traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


# Run bot
with open("./.token") as file:
    token = file.read()

bot.run(token)
