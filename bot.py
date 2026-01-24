import discord
from discord.ext import commands
from discord.ui import View, Button
import asyncio
import json
import os

TOKEN = os.getenv("DISCORD_TOKEN")

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)

DATA_FILE = "chain_state.json"
LEADER_ROLE_NAME = "leader"

# -------------------- STATE --------------------
chain_queue = []
current_index = 0
chain_active = False
chain_message_id = None
chain_channel_id = None

# -------------------- UTIL --------------------
def is_leader_member(member: discord.Member):
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

async def notify_turn(channel):
    if not chain_queue:
        return
    user_id = chain_queue[current_index]
    await channel.send(f"🔔 <@{user_id}> it’s your turn!")

# -------------------- BUTTON VIEW --------------------
class ChainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Participate", style=discord.ButtonStyle.green, custom_id="chain_participate")
    async def participate(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in chain_queue:
            chain_queue.append(interaction.user.id)
            save_state()
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
            await interaction.response.send_message("👋 You left the chain.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ You aren’t in the chain.", ephemeral=True)

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
        await interaction.response.send_message("✅ Hit recorded.", ephemeral=True)
        await notify_turn(interaction.channel)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.red, custom_id="chain_skip")
    async def skip(self, interaction: discord.Interaction, button: Button):
        global current_index
        if not is_leader_member(interaction.user):
            await interaction.response.send_message("❌ Leaders only.", ephemeral=True)
            return

        if not chain_queue:
            await interaction.response.send_message("⚠️ Queue empty.", ephemeral=True)
            return

        current_index = (current_index + 1) % len(chain_queue)
        save_state()
        await interaction.response.send_message("⏭️ Member skipped.", ephemeral=True)
        await notify_turn(interaction.channel)

# -------------------- COMMANDS --------------------
def leader_only():
    async def predicate(ctx):
        return is_leader_member(ctx.author)
    return commands.check(predicate)

@bot.command()
@leader_only()
async def startchain(ctx):
    global chain_message_id, chain_channel_id
    view = ChainView()
    msg = await ctx.send("🔗 **Torn Chain Active**\nJoin below:", view=view)
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
    await notify_turn(ctx.channel)

@bot.command()
@leader_only()
async def stopchain(ctx):
    global chain_active
    chain_active = False
    save_state()
    await ctx.send("⛔ Chain stopped.")

@bot.command()
@leader_only()
async def showqueue(ctx):
    if not chain_queue:
        await ctx.send("📭 Queue empty.")
        return
    mentions = [f"<@{uid}>" for uid in chain_queue]
    await ctx.send("📜 **Current Queue:**\n" + " → ".join(mentions))

@bot.command()
@leader_only()
async def clearchain(ctx, limit: int = 100):
    leader_ids = [
        m.id for m in ctx.guild.members if is_leader_member(m)
    ]

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

# -------------------- EVENTS --------------------
@bot.event
async def on_ready():
    load_state()
    bot.add_view(ChainView())
    print(f"Logged in as {bot.user}")

# -------------------- RUN --------------------
bot.run(TOKEN)
