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
chain_active = False  # Whether the chain has officially started
chain_message_id = None

# ---------- Role check ----------
def is_leader(ctx):
    """Allow only users with the 'Leader' role to run certain commands"""
    return "Leader" in [role.name for role in ctx.author.roles]

# ---------- Start join phase ----------
@bot.command()
@commands.check(is_leader)
async def startchain(ctx):
    """Leader starts the join phase, users can click Participate to join"""
    global chain, current_index, chain_active, chain_message_id
    chain = []
    current_index = 0
    chain_active = False

    embed = discord.Embed(
        title="Torn Chain - Join Phase",
        description="Click **Participate** to join the chain! Leader will start the chain when ready.",
        color=0x00ff00
    )

    class ChainView(discord.ui.View):
        @discord.ui.button(label="Participate", style=discord.ButtonStyle.green)
        async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
            global chain, current_index
            user_id = interaction.user.id
            if user_id not in chain:
                chain.append(user_id)
                mentions = [interaction.guild.get_member(uid).mention for uid in chain]
                embed = discord.Embed(
                    title="Torn Chain - Join Phase",
                    description="Click **Participate** to join the chain!\n\n**Participants:**\n" + "\n".join(mentions),
                    color=0x00ff00
                )
                await interaction.message.edit(embed=embed, view=self)
                await interaction.response.send_message(f"{interaction.user.mention} joined the chain!", ephemeral=True)
            else:
                await interaction.response.send_message("You are already in the chain.", ephemeral=True)

        @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
        async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
            global chain, current_index
            user_id = interaction.user.id
            if user_id in chain:
                idx = chain.index(user_id)
                chain.remove(user_id)
                if idx <= current_index and current_index > 0:
                    current_index -= 1
                mentions = [interaction.guild.get_member(uid).mention for uid in chain]
                embed = discord.Embed(
                    title="Torn Chain - Join Phase",
                    description="Click **Participate** to join the chain!\n\n**Participants:**\n" + "\n".join(mentions),
                    color=0x00ff00
                )
                await interaction.message.edit(embed=embed, view=self)
                await interaction.response.send_message(f"{interaction.user.mention} left the chain.", ephemeral=True)
            else:
                await interaction.response.send_message("You are not in the chain.", ephemeral=True)

        @discord.ui.button(label="Done", style=discord.ButtonStyle.blurple)
        async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
            global current_index
            if not chain_active:
                await interaction.response.send_message("The chain hasn’t started yet! Leader must start it.", ephemeral=True)
                return
            user_id = interaction.user.id
            if user_id != chain[current_index]:
                await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
                return
            current_index = (current_index + 1) % len(chain)
            next_user = interaction.guild.get_member(chain[current_index])
            await interaction.response.send_message(f"{next_user.mention}, it's your turn now!", ephemeral=False)
            await interaction.channel.send(f"{next_user.mention} 🔔 It's your turn!")

    # Send the buttons message
    message = await ctx.send(embed=embed, view=ChainView())
    chain_message_id = message.id

    # Pin the buttons message so it stays at the top
    try:
        await message.pin()
    except discord.Forbidden:
        await ctx.send("I don't have permission to pin messages. Please allow me to manage pins.", delete_after=10)
    except discord.HTTPException as e:
        await ctx.send(f"Failed to pin message: {e}", delete_after=10)

@startchain.error
async def startchain_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You need the **Leader** role to start the chain!")

# ---------- Begin chain ----------
@bot.command()
@commands.check(is_leader)
async def beginchain(ctx):
    """Leader starts the chain after participants have joined"""
    global chain_active, current_index
    if not chain:
        await ctx.send("No participants in the chain. Cannot start.")
        return
    chain_active = True
    current_index = 0
    first_user = ctx.guild.get_member(chain[current_index])
    await ctx.send(f"The chain has started! {first_user.mention}, it's your turn! 🔔")

@beginchain.error
async def beginchain_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You need the **Leader** role to begin the chain!")

# ---------- Stop chain ----------
@bot.command()
@commands.check(is_leader)
async def stopchain(ctx):
    global chain, current_index, chain_active, chain_message_id
    chain = []
    current_index = 0
    chain_active = False
    # Delete and unpin the buttons message
    if chain_message_id:
        try:
            msg = await ctx.channel.fetch_message(chain_message_id)
            await msg.unpin()
            await msg.delete()
        except:
            pass
    chain_message_id = None
    await ctx.send("Chain stopped by Leader.")

# ---------- Clear bot messages including leader commands ----------
@bot.command()
@commands.check(is_leader)
async def clearchain(ctx, limit: int = 50):
    """Clear bot messages including leader command messages, but keep the buttons message pinned"""
    global chain_message_id

    def is_deletable(m):
        # Delete all bot messages except the pinned buttons message
        return m.author == bot.user and m.id != chain_message_id

    try:
        deleted = await ctx.channel.purge(limit=limit, check=is_deletable)
        await ctx.send(f"Cleared {len(deleted)} bot messages (buttons kept).", delete_after=5)
    except Exception as e:
        await ctx.send(f"Error while clearing messages: {e}", delete_after=5)

# ---------- Show current queue ----------
@bot.command()
async def showqueue(ctx):
    """Show the current Torn chain queue"""
    global chain, current_index, chain_active
    if not chain:
        await ctx.send("The chain is currently empty.")
        return

    queue_text = ""
    for idx, user_id in enumerate(chain):
        user = ctx.guild.get_member(user_id)
        if not user:
            continue
        if idx == current_index and chain_active:
            queue_text += f"➡️ **{user.display_name}** (current turn)\n"
        else:
            queue_text += f"{user.display_name}\n"

    embed = discord.Embed(
        title="Torn Chain Queue",
        description=queue_text,
        color=0x00ff00
    )
    await ctx.send(embed=embed)

# ---------- Bot ready ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ---------- Run the bot ----------
bot.run(os.getenv("DISCORD_TOKEN"))
