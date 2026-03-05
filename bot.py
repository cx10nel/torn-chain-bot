import discord
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import json
import os
import time

TOKEN = os.getenv("DISCORD_TOKEN")

LEADER_ROLE_NAME = "leader"
DATA_FILE = "chain_state.json"

TURN_TIME = 240
GRACE_TIME = 60

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

chain_queue = []
current_index = 0
chain_active = False
chain_message_id = None
chain_channel_id = None
turn_start_time = None


# ---------------- STATE ----------------

def save_state():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "queue": chain_queue,
            "index": current_index,
            "active": chain_active,
            "message_id": chain_message_id,
            "channel_id": chain_channel_id,
            "turn_start": turn_start_time
        }, f)


def load_state():
    global chain_queue, current_index, chain_active
    global chain_message_id, chain_channel_id, turn_start_time

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)

        chain_queue = data.get("queue", [])
        current_index = data.get("index", 0)
        chain_active = data.get("active", False)
        chain_message_id = data.get("message_id")
        chain_channel_id = data.get("channel_id")
        turn_start_time = data.get("turn_start")


# ---------------- UTIL ----------------

def is_leader(member):
    return any(r.name.lower() == LEADER_ROLE_NAME for r in member.roles)


def progress_bar():

    if not turn_start_time:
        return "Waiting..."

    elapsed = int(time.time()) - turn_start_time
    total = TURN_TIME + GRACE_TIME

    remaining = max(total - elapsed, 0)

    percent = min(elapsed / total, 1)

    bars = 20
    filled = int(percent * bars)

    bar = "█" * filled + "░" * (bars - filled)

    mins = remaining // 60
    secs = remaining % 60

    if elapsed < TURN_TIME:
        phase = "Hit Window"
    elif elapsed < total:
        phase = "Grace Period"
    else:
        phase = "Skipping..."

    return f"`{bar}`\n{phase} – {mins}m {secs}s remaining"


# ---------------- EMBED ----------------

async def update_chain_message(guild):

    if not chain_message_id:
        return

    channel = guild.get_channel(chain_channel_id)

    try:
        msg = await channel.fetch_message(chain_message_id)
    except:
        return

    if not chain_queue:
        queue_text = "No participants yet."
    else:

        lines = []

        for i, uid in enumerate(chain_queue):

            marker = "🎯" if chain_active and i == current_index else "•"

            lines.append(f"{marker} **{i+1}.** <@{uid}>")

        queue_text = "\n".join(lines)

    embed = discord.Embed(
        title="🔗 Torn Chain Manager",
        color=discord.Color.green() if chain_active else discord.Color.red()
    )

    status = "🟢 Active" if chain_active else "⛔ Not Active"

    embed.add_field(name="Status", value=status, inline=False)

    if chain_active:
        embed.add_field(name="Turn Timer", value=progress_bar(), inline=False)

    embed.add_field(name="Queue", value=queue_text, inline=False)

    embed.set_footer(text="Use buttons below to join, leave, or mark your hit.")

    await msg.edit(embed=embed, view=ChainView())


# ---------------- TIMER ----------------

async def notify_turn(channel):

    global turn_start_time

    user_id = chain_queue[current_index]

    turn_start_time = int(time.time())

    save_state()

    hit_end = turn_start_time + TURN_TIME
    skip_time = turn_start_time + TURN_TIME + GRACE_TIME

    await channel.send(
        f"🔔 <@{user_id}> it's your turn!\n"
        f"🕓 Hit deadline: <t:{hit_end}:R>\n"
        f"⚠️ Skip at: <t:{skip_time}:R>"
    )

    bot.loop.create_task(turn_timer(channel))


async def turn_timer(channel):

    await asyncio.sleep(TURN_TIME)

    if not chain_active:
        return

    await channel.send("⚠️ Hit window expired. Grace period started.")

    await asyncio.sleep(GRACE_TIME)

    if not chain_active:
        return

    global current_index

    current_index = (current_index + 1) % len(chain_queue)

    save_state()

    await channel.send("⏭️ User skipped.")

    await update_chain_message(channel.guild)

    await notify_turn(channel)


# ---------------- BUTTONS ----------------

class ChainView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Participate", style=discord.ButtonStyle.green, custom_id="join")
    async def join(self, interaction, button):

        if interaction.user.id not in chain_queue:

            chain_queue.append(interaction.user.id)

            save_state()

            await update_chain_message(interaction.guild)

            await interaction.response.send_message("Joined chain.", ephemeral=True)

        else:

            await interaction.response.send_message("Already in chain.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.gray, custom_id="leave")
    async def leave(self, interaction, button):

        global current_index

        if interaction.user.id in chain_queue:

            idx = chain_queue.index(interaction.user.id)

            chain_queue.remove(interaction.user.id)

            if idx <= current_index and current_index > 0:
                current_index -= 1

            save_state()

            await update_chain_message(interaction.guild)

            await interaction.response.send_message("Left chain.", ephemeral=True)

        else:

            await interaction.response.send_message("Not in chain.", ephemeral=True)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.blurple, custom_id="done")
    async def done(self, interaction, button):

        global current_index

        if not chain_active:
            await interaction.response.send_message("Chain not active.", ephemeral=True)
            return

        if chain_queue[current_index] != interaction.user.id:
            await interaction.response.send_message("Not your turn.", ephemeral=True)
            return

        current_index = (current_index + 1) % len(chain_queue)

        save_state()

        await update_chain_message(interaction.guild)

        await interaction.response.send_message("Hit recorded.", ephemeral=True)

        await notify_turn(interaction.channel)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.red, custom_id="skip")
    async def skip(self, interaction, button):

        if not is_leader(interaction.user):
            await interaction.response.send_message("Leaders only.", ephemeral=True)
            return

        global current_index

        current_index = (current_index + 1) % len(chain_queue)

        save_state()

        await update_chain_message(interaction.guild)

        await interaction.response.send_message("Skipped.", ephemeral=True)

        await notify_turn(interaction.channel)


# ---------------- COMMAND CHECK ----------------

def leader_only():
    async def predicate(ctx):
        return is_leader(ctx.author)
    return commands.check(predicate)


# ---------------- COMMANDS ----------------

@bot.command()
@leader_only()
async def startchain(ctx):

    global chain_message_id, chain_channel_id

    view = ChainView()

    embed = discord.Embed(
        title="🔗 Torn Chain Manager",
        description="Queue empty. Press Participate to join.",
        color=discord.Color.red()
    )

    msg = await ctx.send(embed=embed, view=view)

    await msg.pin()

    chain_message_id = msg.id
    chain_channel_id = ctx.channel.id

    save_state()


@bot.command()
@leader_only()
async def beginchain(ctx):

    global chain_active, current_index

    if not chain_queue:
        await ctx.send("Queue empty.")
        return

    chain_active = True
    current_index = 0

    save_state()

    await update_chain_message(ctx.guild)

    await notify_turn(ctx.channel)


@bot.command()
@leader_only()
async def stopchain(ctx):

    global chain_active, chain_queue, current_index

    chain_active = False
    chain_queue.clear()
    current_index = 0

    save_state()

    await update_chain_message(ctx.guild)

    await ctx.send("Chain stopped.")


@bot.command()
async def chainbuttons(ctx):

    embed = discord.Embed(
        title="Chain Controls",
        description="Use the buttons below to interact with the chain.",
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed, view=ChainView())


@bot.command()
@leader_only()
async def clearchain(ctx):

    def should_delete(msg):

        if msg.id == chain_message_id:
            return False

        if msg.author == bot.user:
            return True

        if msg.content.startswith("!"):
            return True

        return False

    deleted = await ctx.channel.purge(limit=200, check=should_delete)

    await ctx.send(f"Cleaned {len(deleted)} messages.", delete_after=5)


# ---------------- LIVE TIMER ----------------

async def live_timer():

    await bot.wait_until_ready()

    while not bot.is_closed():

        if chain_active and chain_channel_id:

            for guild in bot.guilds:
                await update_chain_message(guild)

        await asyncio.sleep(10)


# ---------------- STARTUP ----------------

@bot.event
async def on_ready():

    load_state()

    bot.add_view(ChainView())

    bot.loop.create_task(live_timer())

    print("Bot ready.")


bot.run(TOKEN)
