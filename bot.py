import discord
from discord.ext import commands
from discord.ui import View, Button
import json
import os

# ---------- CONFIG ----------
TOKEN = os.getenv("DISCORD_TOKEN")
LEADER_ROLE_NAME = "leader"
DATA_FILE = "chain_state.json"

# ---------- INTENTS ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- STATE ----------
chain_queue = []
current_index = 0
chain_active = False
chain_message_id = None
chain_channel_id = None

# ---------- UTIL ----------
def is_leader(member: discord.Member):
    return any(r.name.lower() == LEADER_ROLE_NAME for r in member.roles)

def save_state():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "queue": chain_queue,
            "index": current_index,
            "active": chain_active,
            "message_id": chain_message_id,
            "channel_id": chain_channel_id
        }, f)

def load_state():
    global chain_queue, current_index, chain_active, chain_message_id, chain_channel_id
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            chain_queue = data.get("queue", [])
            current_index = data.get("index", 0)
            chain_active = data.get("active", False)
            chain_message_id = data.get("message_id")
            chain_channel_id = data.get("channel_id")

async def update_chain_message(guild: discord.Guild):
    if not chain_message_id or not chain_channel_id:
        return

    channel = guild.get_channel(chain_channel_id)
    if not channel:
        return

    try:
        msg = await channel.fetch_message(chain_message_id)
    except:
        return

    if not chain_queue:
        queue_text = "No participants yet."
    else:
        lines = []
        for i, uid in enumerate(chain_queue):
            marker = " ⬅️ **CURRENT**" if chain_active and i == current_index else ""
            lines.append(f"{i+1}. <@{uid}>{marker}")
        queue_text = "\n".join(lines)

    status = "🟢 Active" if chain_active else "⛔ Not active"

    embed = discord.Embed(
        title="🔗 Torn Chain",
        description=f"**Status:** {status}\n\n**Queue:**\n{queue_text}",
        color=discord.Color.green() if chain_active else discord.Color.red()
    )

    await msg.edit(embed=embed)

async def notify_turn(channel: discord.TextChannel):
    if not chain_queue:
        return
    await channel.send(f"🔔 <@{chain_queue[current_index]}> it’s your turn!")

# ---------- BUTTON VIEW ----------
class ChainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Participate", style=discord.ButtonStyle.green, custom_id="chain_join")
    async def participate(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in chain_queue:
            chain_queue.append(interaction.user.id)
            save_state()
            await update_chain_message(interaction.guild)
            await interaction.response.send_message("✅ You joined the chain.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ You’re already in the chain.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.gray, custom_id="chain_leave")
    async def leave(self, interaction: discord.Interaction, button: Button):
        global current_index
        if interaction.user.id in chain_queue:
            idx = chain_queue.index(interaction.user.id)
            chain_queue.remove(interaction.user.id)
            if idx <= current_index and current_index > 0:
                current_index -= 1
            save_state()
            await update_chain_message(interaction.guild)
            await interaction.response.send_message("👋 You left the chain.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ You’re not in the chain.", ephemeral=True)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.blurple, custom_id="chain_done")
    async def done(self, interaction: discord.Interaction, button: Button):
        global current_index
        if not chain_active:
            await interaction.response.send_message("❌ Chain not active.", ephemeral=True)
            return

        if chain_queue[current_index] != interaction.user.id:
            await interaction.response.send_message("⏳ It’s not your turn.", ephemeral=True)
            return

        current_index = (current_index + 1) % len(chain_queue)
        save_state()
        await update_chain_message(interaction.guild)
        await interaction.response.send_message("✅ Hit recorded.", ephemeral=True)
        await notify_turn(interaction.channel)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.red, custom_id="chain_skip")
    async def skip(self, interaction: discord.Interaction, button: Button):
        global current_index
        if not is_leader(interaction.user):
            await interaction.response.send_message("❌ Leaders only.", ephemeral=True)
            return

        if not chain_queue:
            await interaction.response.send_message("⚠️ Queue empty.", ephemeral=True)
            return

        current_index = (current_index + 1) % len(chain_queue)
        save_state()
        await update_chain_message(interaction.guild)
        await interaction.response.send_message("⏭️ Member skipped.", ephemeral=True)
        await notify_turn(interaction.channel)

# ---------- CHECK ----------
def leader_only():
    async def predicate(ctx):
        return is_leader(ctx.author)
    return commands.check(predicate)

# ---------- COMMANDS ----------
@bot.command()
@leader_only()
async def startchain(ctx):
    global chain_message_id, chain_channel_id
    view = ChainView()
    embed = discord.Embed(
        title="🔗 Torn Chain",
        description="**Status:** ⛔ Not active\n\n**Queue:**\nNo participants yet.",
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
        await ctx.send("⚠️ No participants.")
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

    try:
        msg = await ctx.channel.fetch_message(chain_message_id)
        await msg.edit(view=None)
    except:
        pass

    await update_chain_message(ctx.guild)
    await ctx.send("⛔ Chain stopped and participants cleared.")

@bot.command()
@leader_only()
async def showqueue(ctx):
    if not chain_queue:
        await ctx.send("📭 Queue empty.")
        return

    lines = []
    for i, uid in enumerate(chain_queue):
        marker = " ⬅️ CURRENT" if chain_active and i == current_index else ""
        lines.append(f"{i+1}. <@{uid}>{marker}")

    await ctx.send("📜 **Current Queue:**\n" + "\n".join(lines))

@bot.command()
@leader_only()
async def clearchain(ctx, limit: int = 100):
    leader_ids = [m.id for m in ctx.guild.members if is_leader(m)]

    def check(m: discord.Message):
        if m.id == chain_message_id:
            return False
        if m.author == bot.user:
            return True
        if m.author.id in leader_ids and m.content.startswith("!"):
            return True
        return False

    await ctx.channel.purge(limit=limit, check=check)
    await ctx.send("🧹 Chain messages cleared.", delete_after=5)

# ---------- EVENTS ----------
@bot.event
async def on_ready():
    load_state()
    bot.add_view(ChainView())
    print(f"Logged in as {bot.user}")

# ---------- RUN ----------
bot.run(TOKEN)
