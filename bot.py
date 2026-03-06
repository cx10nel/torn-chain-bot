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
queue = []  # store user IDs
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

async def queue_text():
    if not queue:
        return "No one in queue yet."
    lines = []
    for i, user_id in enumerate(queue):
        user = bot.get_user(user_id)
        if user:
            lines.append(f"{i+1}. {user.name}")
        else:
            lines.append(f"{i+1}. Unknown User")
    return "\n".join(lines)

async def update_chain_message():
    global chain_message
    if not chain_message:
        return

    time_left = CHAIN_DURATION - (time.time() - chain_start) if chain_start else CHAIN_DURATION
    time_left = max(0, time_left)

    bar = build_bar(time_left)
    text = f"""
🔥 **Chain Active**

⏳ Time Left: {int(time_left)}s  
{bar}

**Queue**
{await queue_text()}
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

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green, custom_id="chain_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in queue:
            queue.append(user_id)
            await update_chain_message()
            await interaction.response.send_message("✅ You joined the chain!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Already in queue.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red, custom_id="chain_leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in queue:
            queue.remove(user_id)
            await update_chain_message()
            await interaction.response.send_message("👋 You left the chain.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Not in queue.", ephemeral=True)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.blurple, custom_id="chain_done")
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        global chain_start
        user_id = interaction.user.id
        if queue and queue[0] == user_id:
            queue.pop(0)
            chain_start = time.time()
            await update_chain_message()
            await interaction.response.send_message("✅ Turn completed.", ephemeral=True)
        else:
            await interaction.response.send_message("⏳ Not your turn.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.gray, custom_id="chain_skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        global chain_start
        if queue:
            queue.pop(0)
            chain_start = time.time()
            await update_chain_message()
            await interaction.response.send_message("⏭️ Player skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Queue empty.", ephemeral=True)

    @discord.ui.button(label="Clear Queue", style=discord.ButtonStyle.gray, custom_id="chain_clear")
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

    if not chain_message:
        chain_message = await ctx.send("Starting chain...", view=chain_view)
    else:
        try:
            await chain_message.edit(content="Starting chain...", view=chain_view)
        except discord.errors.NotFound:
            chain_message = await ctx.send("Starting chain...", view=chain_view)

    await update_chain_message()

@bot.command()
async def queue_cmd(ctx):
    """Show the current queue."""
    await ctx.send(f"**Current Queue**\n{await queue_text()}")

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
    if not timer_update.is_running():
        timer_update.start()

# -------------------------
# Run Bot
# -------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not set in Railway variables")

bot.run(TOKEN)
