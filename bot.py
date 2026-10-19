"""Points & deadlines bot. Run with:  python bot.py"""
import calendar
import datetime as dt
import os
import traceback
from typing import Optional
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

import db
import personality as p

# ---------- config (from .env) ----------
load_dotenv()


def _opt_int(name):
    value = os.getenv(name, "").strip()
    return int(value) if value else None


TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = _opt_int("GUILD_ID")
if not TOKEN or not GUILD_ID:
    raise SystemExit("Set DISCORD_TOKEN and GUILD_ID in your .env file first.")

TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "America/Chicago"))
STANDINGS_CHANNEL_ID = _opt_int("STANDINGS_CHANNEL_ID")  # optional: live pinned leaderboard
REMINDER_CHANNEL_ID = _opt_int("REMINDER_CHANNEL_ID")    # optional: deadline reminders
REMIND_HOURS_BEFORE = int(os.getenv("REMIND_HOURS_BEFORE", "24"))
BIRTHDAY_CHANNEL_ID = _opt_int("BIRTHDAY_CHANNEL_ID")    # optional: birthday announcements
BIRTHDAY_HOUR = int(os.getenv("BIRTHDAY_HOUR", "9"))     # hour of day (in TIMEZONE) to announce

GUILD = discord.Object(id=GUILD_ID)
ADMIN_ONLY = discord.Permissions(manage_guild=True)
MAX_LEADERBOARD_ROWS = 50
EMBED_COLOR = 0xFF6EC7

# Roles (besides Manage Server) that may set or remove other members' birthdays.
MOD_ROLES = ("lead", "mod")

# ---------- bot setup ----------
intents = discord.Intents.default()
intents.members = True  # needed to show display names; enable "Server Members Intent" in the portal
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def setup_hook():
    db.init()
    bot.tree.add_command(points_group)
    bot.tree.add_command(deadline_group)
    bot.tree.add_command(birthday_group)
    # Syncing to one server makes new/changed commands show up instantly.
    bot.tree.copy_global_to(guild=GUILD)
    await bot.tree.sync(guild=GUILD)
    reminder_loop.start()
    birthday_loop.start()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID {bot.user.id})")
    await update_standings()


# ---------- helpers ----------

async def name_of(guild, user_id):
    member = guild.get_member(user_id) if guild else None
    if member:
        return member.display_name
    try:
        return (await bot.fetch_user(user_id)).name
    except discord.NotFound:
        return f"Unknown user ({user_id})"


def format_entry(row):
    reason = discord.utils.escape_markdown(row["reason"])
    return f"`{row['amount']:+d}` {reason} · <t:{row['created_at']}:d>"


async def leaderboard_embed(guild, live=False):
    board = db.ranked()
    embed = discord.Embed(title="Live Standings" if live else "Leaderboard", color=EMBED_COLOR)
    if not board:
        embed.description = p.line("leaderboard_empty")
        return embed
    rows = []
    for rank, user_id, total in board[:MAX_LEADERBOARD_ROWS]:
        name = discord.utils.escape_markdown(await name_of(guild, user_id))
        rows.append(f"`#{rank}` **{name}** — {total} pts")
    intro = "" if live else p.line("leaderboard_intro") + "\n\n"
    embed.description = intro + "\n".join(rows)
    if live:
        embed.set_footer(text="Last updated")
        embed.timestamp = discord.utils.utcnow()
    return embed


async def update_standings():
    """Keep one pinned leaderboard message in the standings channel up to date."""
    if not STANDINGS_CHANNEL_ID:
        return
    channel = bot.get_channel(STANDINGS_CHANNEL_ID)
    if channel is None:
        print("STANDINGS_CHANNEL_ID is set but the bot can't see that channel.")
        return
    embed = await leaderboard_embed(channel.guild, live=True)
    try:
        message_id = db.get_setting("standings_message_id")
        if message_id:
            try:
                message = await channel.fetch_message(int(message_id))
                await message.edit(embed=embed)
                return
            except discord.NotFound:
                pass  # someone deleted it; post a new one below
        message = await channel.send(embed=embed)
        db.set_setting("standings_message_id", str(message.id))
        try:
            await message.pin()
        except discord.Forbidden:
            print("Can't pin the standings message (needs Manage Messages). Posted it anyway.")
    except discord.HTTPException as e:
        print(f"Couldn't update standings: {e}")


async def change_points(interaction, member, delta, reason):
    leader_before = db.leader()
    db.add_points(member.id, delta, reason, interaction.user.id)
    rank, total, _ = db.standing(member.id)
    leader_after = db.leader()

    kind = "added" if delta > 0 else "removed"
    text = p.line(kind, user=member.mention, amount=abs(delta), total=total, rank=rank)
    if leader_after is not None and leader_after != leader_before:
        text += "\n\n" + p.line("new_leader", user=f"<@{leader_after}>")

    embed = discord.Embed(description=text, color=EMBED_COLOR)
    embed.set_footer(text=f"Reason: {reason}  •  Total: {total} pts  •  Rank #{rank}")
    await interaction.response.send_message(embed=embed)
    await update_standings()


def parse_due(date, time):
    """'2026-10-23' + '23:59' in the server timezone -> unix timestamp, or None if invalid."""
    try:
        when = dt.datetime.strptime(f"{date.strip()} {time.strip()}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return int(when.replace(tzinfo=TIMEZONE).timestamp())


def now_ts():
    return int(dt.datetime.now(dt.timezone.utc).timestamp())


# ---------- /points (admins) ----------

points_group = app_commands.Group(
    name="points", description="Add or remove points", default_permissions=ADMIN_ONLY
)


@points_group.command(name="add", description="Give points to a member")
@app_commands.describe(member="Who gets the points", amount="How many points",
                       reason="What for (e.g. EOTW win, H2HFT round 1)")
async def points_add(interaction: discord.Interaction, member: discord.Member,
                     amount: app_commands.Range[int, 1, 1000],
                     reason: app_commands.Range[str, 1, 200]):
    await change_points(interaction, member, amount, reason)


@points_group.command(name="remove", description="Take points from a member")
@app_commands.describe(member="Who loses the points", amount="How many points",
                       reason="Why (e.g. troll edit, H2HFT no-show)")
async def points_remove(interaction: discord.Interaction, member: discord.Member,
                        amount: app_commands.Range[int, 1, 1000],
                        reason: app_commands.Range[str, 1, 200]):
    await change_points(interaction, member, -amount, reason)


# ---------- /leaderboard, /profile, /history (everyone) ----------

@bot.tree.command(name="leaderboard", description="See the current standings")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    await interaction.followup.send(embed=await leaderboard_embed(interaction.guild))


@bot.tree.command(name="profile", description="See a member's points, rank, and recent activity")
@app_commands.describe(member="Whose profile (leave blank for your own)")
async def profile(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"{member.display_name}'s Profile", color=EMBED_COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)

    standing = db.standing(member.id)
    if standing is None:
        embed.description = p.line("profile_empty", user=member.display_name)
    else:
        rank, total, out_of = standing
        embed.add_field(name="Points", value=str(total))
        embed.add_field(name="Rank", value=f"#{rank} of {out_of}")
        recent = db.history(member.id, limit=5)
        embed.add_field(name="Recent", value="\n".join(format_entry(r) for r in recent), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="history", description="See every point change for a member")
@app_commands.describe(member="Whose history (leave blank for your own)")
async def history(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    shown = 20
    rows = db.history(member.id, limit=shown)
    embed = discord.Embed(title=f"{member.display_name}'s Point History", color=EMBED_COLOR)
    if not rows:
        embed.description = p.line("history_empty", user=member.display_name)
    else:
        embed.description = "\n".join(format_entry(r) for r in rows)
        count = db.history_count(member.id)
        if count > shown:
            embed.set_footer(text=f"Showing the latest {shown} of {count} changes")
    await interaction.response.send_message(embed=embed)


# ---------- /deadline (admins) and /deadlines (everyone) ----------

deadline_group = app_commands.Group(
    name="deadline", description="Add or remove deadlines", default_permissions=ADMIN_ONLY
)


@deadline_group.command(name="add", description="Create a deadline")
@app_commands.describe(name="e.g. EOTW Week 2, H2HFT Round 1",
                       date="Date as YYYY-MM-DD (e.g. 2026-10-23)",
                       time="24-hour time as HH:MM (default 23:59)",
                       description="Optional details")
async def deadline_add(interaction: discord.Interaction,
                       name: app_commands.Range[str, 1, 100], date: str,
                       time: str = "23:59", description: Optional[str] = None):
    due = parse_due(date, time)
    if due is None:
        await interaction.response.send_message(
            "Couldn't read that date/time. Use `YYYY-MM-DD` and `HH:MM`, like `2026-10-23` and `18:00`.",
            ephemeral=True)
        return
    if due <= now_ts():
        await interaction.response.send_message("That time is already in the past.", ephemeral=True)
        return
    if not db.add_deadline(name, due, description):
        await interaction.response.send_message(
            f"A deadline called **{name}** already exists. Remove it first or pick another name.",
            ephemeral=True)
        return
    embed = discord.Embed(description=p.line("deadline_added", name=name, when=f"<t:{due}:F> (<t:{due}:R>)"),
                          color=EMBED_COLOR)
    if description:
        embed.add_field(name="Details", value=description)
    await interaction.response.send_message(embed=embed)


@deadline_group.command(name="remove", description="Delete a deadline")
@app_commands.describe(name="Which deadline")
async def deadline_remove(interaction: discord.Interaction, name: str):
    if db.remove_deadline(name):
        await interaction.response.send_message(f"Removed **{name}**.")
    else:
        await interaction.response.send_message(f"No deadline called **{name}**.", ephemeral=True)


@deadline_remove.autocomplete("name")
async def deadline_name_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=d["name"], value=d["name"])
            for d in db.deadlines_after(0) if current.lower() in d["name"].lower()][:25]


@bot.tree.command(name="deadlines", description="See upcoming deadlines")
async def deadlines(interaction: discord.Interaction):
    upcoming = db.deadlines_after(now_ts())
    embed = discord.Embed(title="Upcoming Deadlines", color=EMBED_COLOR)
    if not upcoming:
        embed.description = p.line("no_deadlines")
    else:
        for d in upcoming[:25]:
            value = f"<t:{d['due_at']}:F> · <t:{d['due_at']}:R>"
            if d["description"]:
                value += f"\n{d['description']}"
            embed.add_field(name=d["name"], value=value, inline=False)
    await interaction.response.send_message(embed=embed)


# ---------- /birthday and /birthdays (everyone) ----------

def birthday_in(month, day, year):
    """The date a birthday falls on in a given year. Feb 29 moves to Feb 28 in non-leap years."""
    if (month, day) == (2, 29) and not calendar.isleap(year):
        return dt.date(year, 2, 28)
    return dt.date(year, month, day)


def next_birthday(month, day, today):
    """The next time this birthday comes around, counting today."""
    date = birthday_in(month, day, today.year)
    return date if date >= today else birthday_in(month, day, today.year + 1)


def is_mod(member):
    return member.guild_permissions.manage_guild or any(r.name.lower() in MOD_ROLES for r in member.roles)


async def check_birthday_target(interaction, member):
    """Whose birthday to change: yourself by default, anyone else only for mods. None if refused."""
    member = member or interaction.user
    if member.id != interaction.user.id and not is_mod(interaction.user):
        await interaction.response.send_message("Only mods can change someone else's birthday.", ephemeral=True)
        return None
    return member


birthday_group = app_commands.Group(name="birthday", description="Set or remove your birthday")


@birthday_group.command(name="set", description="Save your birthday (month and day only)")
@app_commands.describe(month="Month as a number (1-12)", day="Day of the month",
                       member="Mods only: whose birthday (leave blank for your own)")
async def birthday_set(interaction: discord.Interaction, month: app_commands.Range[int, 1, 12],
                       day: app_commands.Range[int, 1, 31], member: Optional[discord.Member] = None):
    member = await check_birthday_target(interaction, member)
    if member is None:
        return
    try:
        dt.date(2000, month, day)  # 2000 is a leap year, so Feb 29 is allowed
    except ValueError:
        await interaction.response.send_message(
            f"{calendar.month_name[month]} doesn't have a day {day}.", ephemeral=True)
        return
    db.set_birthday(member.id, month, day)
    embed = discord.Embed(description=p.line("birthday_set", user=member.mention), color=EMBED_COLOR)
    embed.set_footer(text=f"Birthday: {calendar.month_name[month]} {day}")
    await interaction.response.send_message(embed=embed)


@birthday_group.command(name="remove", description="Forget your birthday")
@app_commands.describe(member="Mods only: whose birthday (leave blank for your own)")
async def birthday_remove(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = await check_birthday_target(interaction, member)
    if member is None:
        return
    if db.remove_birthday(member.id):
        await interaction.response.send_message(f"Removed {member.display_name}'s birthday.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{member.display_name} has no birthday saved.", ephemeral=True)


@bot.tree.command(name="birthdays", description="See the next 10 upcoming birthdays")
async def birthdays(interaction: discord.Interaction):
    today = dt.datetime.now(TIMEZONE).date()
    upcoming = sorted(
        (next_birthday(b["month"], b["day"], today), b["user_id"]) for b in db.all_birthdays()
        if interaction.guild.get_member(b["user_id"])  # skip people who left
    )[:10]
    embed = discord.Embed(title="Upcoming Birthdays", color=EMBED_COLOR)
    if not upcoming:
        embed.description = p.line("no_birthdays")
    else:
        rows = []
        for date, user_id in upcoming:
            name = discord.utils.escape_markdown(await name_of(interaction.guild, user_id))
            days = (date - today).days
            when = "today!!" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
            rows.append(f"**{name}**: {calendar.month_name[date.month]} {date.day} ({when})")
        embed.description = "\n".join(rows)
    await interaction.response.send_message(embed=embed)


# ---------- /help (everyone) ----------

def usage(cmd):
    """'/points add @member amount reason' style usage, with [optional] params in brackets."""
    parts = [f"/{cmd.qualified_name}"]
    for param in cmd.parameters:
        name = f"@{param.name}" if param.type == discord.AppCommandOptionType.user else param.name
        parts.append(name if param.required else f"[{name}]")
    return " ".join(parts)


@bot.tree.command(name="help", description="See every command and how to use it")
async def help_command(interaction: discord.Interaction):
    everyone, mods = [], []
    for cmd in bot.tree.walk_commands():
        if isinstance(cmd, app_commands.Group):
            continue
        locked = (cmd.root_parent or cmd).default_permissions is not None
        (mods if locked else everyone).append(f"`{usage(cmd)}`\n{cmd.description}")
    embed = discord.Embed(title="Commands", description=p.line("help_intro"), color=EMBED_COLOR)
    embed.add_field(name="Everyone", value="\n".join(everyone), inline=False)
    if mods:
        embed.add_field(name="Mods and above", value="\n".join(mods), inline=False)
    await interaction.response.send_message(embed=embed)


# ---------- reminders ----------

@tasks.loop(minutes=10)
async def reminder_loop():
    if not REMINDER_CHANNEL_ID:
        return
    channel = bot.get_channel(REMINDER_CHANNEL_ID)
    if channel is None:
        return
    for d in db.deadlines_needing_reminder(now_ts(), REMIND_HOURS_BEFORE * 3600):
        text = p.line("deadline_reminder", name=d["name"], when=f"<t:{d['due_at']}:R>")
        try:
            await channel.send(embed=discord.Embed(description=text, color=EMBED_COLOR))
            db.mark_reminded(d["id"])
        except discord.HTTPException as e:
            print(f"Couldn't send reminder for {d['name']}: {e}")


@reminder_loop.before_loop
async def before_reminders():
    await bot.wait_until_ready()


# ---------- birthday announcements ----------

@tasks.loop(minutes=10)
async def birthday_loop():
    if not BIRTHDAY_CHANNEL_ID:
        return
    now = dt.datetime.now(TIMEZONE)
    if now.hour < BIRTHDAY_HOUR:
        return
    channel = bot.get_channel(BIRTHDAY_CHANNEL_ID)
    if channel is None:
        return  # can't see the channel; try again next loop
    today = now.date()
    todays = [b for b in db.all_birthdays() if birthday_in(b["month"], b["day"], today.year) == today]
    # last_announced_year means a restart never announces the same birthday twice.
    for b in todays:
        if b["last_announced_year"] == today.year:
            continue
        member = channel.guild.get_member(b["user_id"])
        if member is None:
            continue  # left the server
        try:
            await channel.send(p.line("birthday", user=member.mention))
        except discord.HTTPException as e:
            print(f"Couldn't announce {member}'s birthday: {e}")
            continue  # not marked, so the next loop tries again
        db.mark_birthday_announced(member.id, today.year)


@birthday_loop.before_loop
async def before_birthdays():
    await bot.wait_until_ready()


# ---------- errors ----------

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    traceback.print_exception(type(error), error, error.__traceback__)
    message = "Something went wrong running that command. Check the bot's console for details."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


if __name__ == "__main__":
    bot.run(TOKEN)
