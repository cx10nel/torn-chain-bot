import os
import discord
from discord.ext import commands

# ---------- Intents ----------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# ---------- Bot setup ----------
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Chain storage ----------
chain = []
current_index = 0
chain_message_id = None

# ---------- Role check ----------
def is_leader(ctx):
    return "Leader" in [role.name for role in ctx.author.roles]

# ---------- Start chain ----------
@bot.command()
@commands.check(is_leader)
async def startchain(ctx):
    global chain, current_index, chain_message_id
    chain = []
    current_index = 0

    embed = discord.Embed(
        title="Torn Chain Started",
        description="Click **Participate** to join the chain!",
        color=0x00ff00
    )

    # Create buttons
    class ChainView(discord.ui.View):
        @discord.ui.button(label="Participate", style=discord.ButtonStyle.green)
        async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = interaction.user.id
            if user_id not in chain:
                chain.append(user_id)
                await interaction.response.send_message(f"{interaction.user.mention} joined the chain!", ephemeral=True)
            else:
                await interaction.response.send_message("You are already in the chain.", ephemeral=True)

        @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
        async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = interaction.user.id
            if user_id in chain:
                idx = chain.index(user_id)
                chain.remove(user_id)
                global current_index
                # Adjust current_index if needed
                if idx <= current_index and current_index > 0:
                    current_index -= 1
                await interaction.response.send_message(f"{interaction.user.mention} left the chain.", ephemeral=True)
            else:
                await interaction.response.send_message("You are not in the chain.", ephemeral=True)

        @discord.ui.button(label="Done", style=discord.ButtonStyle.blurple)
        async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
            global current_index
            user_id = interaction.user.id
            if not chain:
                await interaction.response.send_message("The chain is empty.", ephemeral=True)
                return
            if user_id != chain[current_index]:
                await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
                return

            # Rotate to next user
            current_index = (current_index + 1) % len(chain)
            next_user = interaction.guild.get_member(chain[current_index])
            await interaction.response.send_message(f"{next_user.mention}, it's your turn now!", ephemeral=False)
            # Ping the next user in the channel
            await interaction.channel.send(f"{next_user.mention} 🔔 It's your turn!")

    message = await ctx.send(embed=embed, view=ChainView())
    chain_message_id = message.id

@startchain.error
async def startchain_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You need the **Leader** role to start the chain!")

# ---------- Stop chain ----------
@bot.command()
@commands.check(is_leader)
async def stopchain(ctx):
    global chain, current_index, chain_message_id
    chain = []
    current_index = 0
    chain_message_id = None
    await ctx.send("Chain stopped by Leader.")

@stopchain.error
async def stopchain_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You need the **Leader** role to stop the chain!")

# ---------- Clear bot messages ----------
@bot.command()
@commands.check(is_leader)
async def clearchain(ctx, limit: int = 50):
    def is_bot_msg(m):
        return m.author == bot.user
    deleted = await ctx.channel.purge(limit=limit, check=is_bot_msg)
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
