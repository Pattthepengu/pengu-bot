import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import sqlite3
import math
from datetime import datetime
import random

# Bot settings
TOKEN = "MTk3MDkzNTM5NTIyNDEyNTQ0.GbPR0c.RUIJ8D4bF3Om5s8-XKnumMY8D2Qxs_aT3LjqDs"
DAILY_CHANNEL_ID = 1252692295518785661
BIRTHDAY_CHANNEL_ID = 1263491036777549834
PREFIX = '!'

# Initialize bot and scheduler
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
scheduler = AsyncIOScheduler()

# Database initialization
def initialize_db():
    # User levels database
    conn = sqlite3.connect('user_levels_xp.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_levels_xp (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

    conn = sqlite3.connect('user_birthdays.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_birthdays (
            user_id INTEGER PRIMARY KEY,
            birthday TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

initialize_db()

def get_user(user_id):
    conn = sqlite3.connect('user_levels_xp.db')
    cursor = conn.cursor()
    cursor.execute('SELECT xp, level FROM user_levels_xp WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_or_update_user(user_id, xp, level):
    conn = sqlite3.connect('user_levels_xp.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_levels_xp (user_id, xp, level)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET xp = ?, level = ?
    ''', (user_id, xp, level, xp, level))
    conn.commit()
    conn.close()

def add_or_update_birthday(user_id, birthday):
    conn = sqlite3.connect('user_birthdays.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_birthdays (user_id, birthday)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET birthday = ?
    ''', (user_id, birthday, birthday))
    conn.commit()
    conn.close()

def remove_birthday(user_id):
    conn = sqlite3.connect('user_birthdays.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_birthdays WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_birthdays():
    conn = sqlite3.connect('user_birthdays.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, birthday FROM user_birthdays')
    birthdays = cursor.fetchall()
    conn.close()
    return birthdays

def get_ordinal_suffix(number):
    if 11 <= number % 100 <= 13:
        return "th"
    elif number % 10 == 1:
        return "st"
    elif number % 10 == 2:
        return "nd"
    elif number % 10 == 3:
        return "rd"
    else:
        return "th"

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    scheduler.start()
    schedule_daily_message()
    schedule_birthday_announcements()

@bot.event
async def on_message(message):
    if message.author.bot or not isinstance(message.channel, discord.TextChannel):
        return

    user_id = message.author.id
    user = get_user(user_id)

    if user is None:
        xp, level = 0, 1
    else:
        xp, level = user

    # Add random XP between 6 and 15
    gained_xp = random.randint(6, 15)
    xp += gained_xp

    # Calculate the XP threshold for the next level
    next_level_threshold = math.floor(50 * (level ** 2))

    # Check if the user levels up
    leveled_up = False
    while xp >= next_level_threshold:
        level += 1
        next_level_threshold = math.floor(50 * (level ** 2))
        leveled_up = True

    # Update the database
    add_or_update_user(user_id, xp, level)

    # If the user leveled up, announce it in the Level Up channel
    if leveled_up:
        level_up_channel = bot.get_channel(1260554844893347861)
        if level_up_channel:
            await level_up_channel.send(
                f"🎉 Congratulations {message.author.mention}! You've reached level {level}! 🎉"
            )

    # Continue processing commands
    await bot.process_commands(message)

@bot.command(name="penguhelp")
async def help_command(ctx):
    # Define the list of commands
    commands = {
        "!level": "Check your current level and XP.",
        "!leaderboard": "Display the leaderboard sorted by levels and XP.",
        "!set_level <@user> <level> <xp>": "Set a user's level and XP (Admin only).",
        "!set_birthday <@user> <DD/MM/YYYY>": "Set a user's birthday (Admin only).",
        "!remove_birthday <@user>": "Remove a user's birthday (Admin only).",
        "!birthdays": "Show upcoming birthdays sorted by soonest.",
        "!send_daily": "Manually send the daily message (Admin only).",
        "!debug_members": "List all visible server members (Admin only).",
    }

    # Create the embed
    embed = discord.Embed(
        title="Bot Commands",
        description="Here is a list of available commands:",
        color=0x00FF00
    )

    for command, description in commands.items():
        embed.add_field(name=command, value=description, inline=False)

    await ctx.send(embed=embed)


@bot.command()
async def level(ctx):
    user_id = ctx.author.id
    user = get_user(user_id)

    if user:
        xp, level = user
        next_level_threshold = math.floor(50 * (level ** 2))
        xp_to_next_level = next_level_threshold - xp
        await ctx.send(
            f"{ctx.author.mention}, you are at level {level} with {xp} XP. "
            f"You need {xp_to_next_level} more XP to reach the next level."
        )
    else:
        await ctx.send(f"{ctx.author.mention}, you haven't earned any XP yet!")

@bot.command()
async def set_level(ctx, user: discord.Member, level: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You do not have permission to use this command.")
        return

    if level < 1:
        await ctx.send("Level must be at least 1.")
        return

    user_id = user.id

    # Calculate the XP for the start of the specified level
    new_xp = math.floor(50 * ((level - 1) ** 2)) if level > 1 else 0

    # Update the user's XP and level in the database
    add_or_update_user(user_id, new_xp, level)

    await ctx.send(
        f"{user.mention}'s level has been set to {level} with {new_xp} XP."
    )

@bot.command()
async def leaderboard(ctx):
    # Fetch leaderboard data from the database
    conn = sqlite3.connect('user_levels_xp.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, xp, level FROM user_levels_xp ORDER BY level DESC, xp DESC')
    leaderboard_data = cursor.fetchall()
    conn.close()

    # Create an embedded message for the leaderboard
    embed = discord.Embed(
        title="Leaderboard",
        description="Top users by level and XP",
        color=0x00FF00
    )

    if leaderboard_data:
        for rank, (user_id, xp, level) in enumerate(leaderboard_data, start=1):
            user = bot.get_user(user_id)
            username = user.name if user else f"Unknown User (ID: {user_id})"
            embed.add_field(
                name=f"#{rank} {username}",
                value=f"**Level:** {level} | **XP:** {xp}",
                inline=False
            )
    else:
        embed.description = "No users found in the leaderboard."

    await ctx.send(embed=embed)
    
@bot.command()
async def set_birthday(ctx, user: discord.Member, birthday: str):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You do not have permission to set other users' birthdays.")
        return

    try:
        datetime.strptime(birthday, "%d/%m/%Y")
        add_or_update_birthday(user.id, birthday)
        await ctx.send(f"{user.mention}'s birthday has been set to {birthday}.")
    except ValueError:
        await ctx.send("Invalid date format! Please use DD/MM/YYYY.")

@bot.command()
async def remove_birthday(ctx, user: discord.Member):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You do not have permission to remove birthdays.")
        return

    remove_birthday(user.id)
    await ctx.send(f"{user.mention}'s birthday has been removed from the database.")

@bot.command()
async def birthdays(ctx):
    birthdays = get_birthdays()
    today = datetime.now()
    birthday_list = []

    for user_id, birthday in birthdays:
        birthday_date = datetime.strptime(birthday, "%d/%m/%Y").replace(year=today.year)
        if birthday_date < today:
            birthday_date = birthday_date.replace(year=today.year + 1)
        days_until = (birthday_date - today).days
        birthday_list.append((user_id, days_until))

    birthday_list.sort(key=lambda x: x[1])
    embed = discord.Embed(title="Upcoming Birthdays", description="User birthdays sorted by soonest", color=0x00ff00)

    for user_id, days_until in birthday_list:
        user = bot.get_user(user_id)
        username = user.name if user else "Unknown User"
        embed.add_field(name=username, value=f"{days_until} days", inline=False)

    await ctx.send(embed=embed)

def schedule_daily_message():
    scheduler.add_job(send_daily_message, 'cron', hour=11, minute=0)

async def send_daily_message():
    channel = bot.get_channel(DAILY_CHANNEL_ID)
    if channel:
        await channel.send(f"Good morning, everyone! Remember to be active and react to everyone's messages. Don't forget to check out <#1258438330186727485> to support everyone in the group.")

def schedule_birthday_announcements():
    scheduler.add_job(check_and_announce_birthdays, 'cron', hour=9, minute=0)

async def check_and_announce_birthdays():
    birthdays = get_birthdays()
    today = datetime.now().strftime("%d/%m/%Y")
    channel = bot.get_channel(BIRTHDAY_CHANNEL_ID)

    if channel:
        for user_id, birthday in birthdays:
            if birthday == today:
                user = bot.get_user(user_id)
                if user:
                    birth_year = int(birthday.split('/')[-1])
                    current_year = datetime.now().year
                    age = current_year - birth_year
                    suffix = get_ordinal_suffix(age)
                    await channel.send(f"🎉 Happy {age}{suffix} Birthday to {user.mention}! 🎂")

bot.run(TOKEN)


