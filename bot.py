import os
import discord
from discord.ext import commands

# Intents setup
intents = discord.Intents.default()
intents.members = True  # Needed to track server members
intents.message_content = True  # Optional: only needed if you want typed commands

# Bot prefix (for typed commands, optional)
bot = commands.Bot(command_prefix="!", intents=intents)

# Data structure to store the chain
chain = []

# Admin check
def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

# Start chain command
@bot.command()
@commands.check(is_admin)
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

# Done command (user has taken their hit)
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

# Leave command
@bot.command()
async def leave(ctx):
    global chain
    if ctx.author.id in chain:
        chain.remove(ctx.author.id)
        await ctx.send(f"{ctx.author.mention} left the chain.")
    else:
        await ctx.send("You're not in the chain!")

# Stop chain (admin only)
@bot.command()
@commands.check(is_admin)
async def stopchain(ctx):
    global chain
    chain = []
    await ctx.send("Chain stopped by admin.")

# Clear previous messages (admin only)
@bot.command()
@commands.check(is_admin)
async def clearchain(ctx, limit: int = 10):
    await ctx.channel.purge(limit=limit)
    await ctx.send("Previous messages cleared.", delete_after=5)

# Event: on_ready
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Run the bot using environment variable
bot.run(os.getenv("DISCORD_TOKEN"))
