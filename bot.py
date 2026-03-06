import discord
from discord.ext import commands, tasks
import asyncio
import time
import os

# -------------------------
# Intents and Bot Setup
# -------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------
# Chain state
# -------------------------
queue = []
chain_message = None
chain_active = False
chain_start = None
CHAIN_DURATION = 60  # seconds per turn

# -------------------------
# Helper functions
# -------------------------
def build_bar(time_left):
    total = 20
    filled = int((time_left / CHAIN_DURATION) * total)
    return "🟩" * filled + "⬜" * (total - filled)

def queue_text():
    if not queue:
        return "No one in queue yet."
    return "\n".join([f"{i+1}. {user.name}" for i, user in enumerate(queue)])

async def update_chain_message():
    global chain_message
    if not chain_message:
        return

    if chain_start:
        elapsed = time.time() - chain_start
        time_left = max(0, CHAIN_DURATION - elapsed)
    else:
        time_left = CHAIN_DURATION

    bar = build_bar(time_left)
    text = f"""
🔥 **Chain Active**

⏳ Time Left: {int(time_left)}s  
{bar}

**Queue**
{queue_text()}
"""
    try:
        await chain_message.edit(content=text)
    except discord.errors.NotFound:
        chain_message = None
    except discord.errors.HTTPException:
        pass

# -------------------------
# Chain Buttons (Persistent View)
# -------------------------
class ChainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user not in queue:
            queue.append(user)
            await update_chain_message()
            await interaction.response.send_message("✅ You joined the chain!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ You are already in the queue.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user in queue:
            queue.remove(user)
            await update_chain_message()
            await interaction.response.send_message("👋 You left the chain.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ You are not in the queue.", ephemeral=True)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.blurple)
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        global chain_start
        user = interaction.user
        if queue and queue[0] == user:
            queue.pop(0)
            chain_start = time.time()
            await update_chain_message()
            await interaction.response.send_message("✅ Turn completed.", ephemeral=True)
        else:
            await interaction.response.send_message("⏳ It's not your turn.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.gray)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        global chain_start
        if queue:
            queue.pop(0)
            chain_start = time.time()
            await update_chain_message()
            await interaction.response.send_message("⏭️ Player skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Queue empty.", ephemeral=True)

    @discord.ui.button(label="Clear Queue", style=discord.ButtonStyle.gray)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue.clear()
        await update_chain_message()
        await interaction.response.send_message("Queue cleared.", ephemeral=True)

# -------------------------
# Persistent View Registration
# -------------------------
chain_view = ChainView()
bot.add_view(chain_view)

# -------------------------
# Timer loop
# -------------------------
@tasks.loop(seconds=3)
async def timer_update():
    if chain_active:
        await update_chain_message()

# -------------------------
# Bot Commands
# -------------------------
@bot.command()
async def startchain(ctx):
    """Start or reset the chain."""
    global chain_message, chain_active, chain_start
    chain_active = True
    chain_start = time.time()

    # Send a new chain message if none exists or old one deleted
    if not chain_message:
        chain_message = await ctx.send("Starting chain...", view=chain_view)
    else:
        try:
            await chain_message.edit(content="Starting chain...", view=chain_view)
        except discord.errors.NotFound:
            chain_message = await ctx.send("Starting chain...", view=chain_view)

    await update_chain_message()

    if not timer_update.is_running():
        timer_update.start()

@bot.command()
async def queue_cmd(ctx):
    """Show the current queue."""
    await ctx.send(f"**Current Queue**\n{queue_text()}")

@bot.command()
async def clearchain(ctx):
    """Clear bot messages and queue."""
    global chain_message
    async for msg in ctx.channel.history(limit=100):
        if msg.author == bot.user and msg != chain_message:
            try:
                await msg.delete()
            except:
                pass
        if msg.content.startswith("!"):
            try:
                await msg.delete()
            except:
                pass
    await ctx.send("Chain cleaned.")

# -------------------------
# Bot Startup
# -------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not set in Railway variables")

bot.run(TOKEN)
