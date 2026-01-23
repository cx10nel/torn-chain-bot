import os
import discord
from discord.ext import commands

# ---------- Intents ----------
intents = discord.Intents.default()
intents.members = True          # Needed to track server members
intents.message_content = True  # Needed to detect typed commands

# ---------- Bot setup ----------
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Chain storage ----------
chain = []

# ---------- Role check function ----------
def is_leader(ctx):
    """Allow command only for members with the 'Leader' role"""
    role_names = [role.name for role in ctx.author.roles]
    return "Leader" in role_names

# ---------- Start chain ----------
@bot.command()
@commands.check(is_leader)
async def startchain(ctx):
    global chain
    chain = []
    embed = discord.Embed(
        title="Torn Chain Started",
        description="Click ✅ to participate!",
        color=0x00ff00
    )
    message = await ctx.send(embed=embed)
    await message.add_reaction("✅")  # Users click to join

@startchain.error
async def startchain_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You need the **Leader** role to start the chain!")

# ---------- Done command ----------
@bot.command()
async def done(ctx):
    global chain
    if ctx.author.id in chain:
        chain.append(chain.pop(0))  # Rotate
        next_user_id = chain[0]
        user = ctx.guild.get_member(next_user_id)
        await ctx.send(f"{user.mention}, it's your turn!")
    else:
        await ctx.send("You're not in the chain!")

# ---------- Leave command ----------
@bot.command()
async def leave(ctx):
    global chain
    if ctx.author.id in chain:
        chain.remove(ctx.author.id)
        await ctx.send(f"{ctx.author.mention} left the chain.")
    else:
        await ctx.send("You're not in the chain!")

# ---------- Stop chain ----------
@bot.command()
@commands.check(is_leader)
async def stopchain(ctx):
    global chain
    chain = []
    await ctx.send("Chain stopped by Leader.")

@stopchain.error
async def stopchain_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You need the **Leader** role to stop the chain!")

# ---------- Clear previous bot messages ----------
@bot.command()
@commands.check(is_leader)
async def clearchain(ctx, limit: int = 10):
    # Only delete messages sent by the bot
    def is_bot_message(message):
        return message.author == bot.user
    deleted = await ctx.channel.purge(limit=limit, check=is_bot_message)
    await ctx.send(f"Cleared {len(deleted)} bot messages.", delete_after=5)

@clearchain.error
async def clearchain_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You need the **Leader** role to clear messages!")

# ---------- Bot ready ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ---------- Run the bot ----------
bot.run(os.getenv("DISCORD_TOKEN"))
