import os
import asyncio
import discord
from discord.ext import commands

# ---------- Intents ----------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Chain State ----------
chain = []
current_index = 0
chain_active = False
chain_message_id = None
chain_view = None
reminder_task = None

REMINDER_SECONDS = 120

# ---------- Role Check ----------
def is_leader_member(member: discord.Member):
    return any(role.name == "Leader" for role in member.roles)

def is_leader(ctx):
    return is_leader_member(ctx.author)

# ---------- Reminder ----------
async def reminder_loop(channel, guild):
    await asyncio.sleep(REMINDER_SECONDS)
    if chain_active and chain:
        user = guild.get_member(chain[current_index])
        if user:
            await channel.send(f"⏱ {user.mention} reminder — please take your hit!")

# ---------- Embed Update ----------
async def update_embed(message, guild):
    mentions = [
        guild.get_member(uid).mention
        for uid in chain
        if guild.get_member(uid)
    ]

    embed = discord.Embed(
        title="Torn Chain",
        description="Click **Participate** to join\n\n**Queue:**\n" + ("\n".join(mentions) if mentions else "—"),
        color=0x00ff00
    )

    await message.edit(embed=embed)

# ---------- Buttons ----------
class ChainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Participate", style=discord.ButtonStyle.green)
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in chain:
            chain.append(interaction.user.id)
            await update_embed(interaction.message, interaction.guild)
            await interaction.response.send_message("You joined the chain!", ephemeral=True)
        else:
            await interaction.response.send_message("You are already in the chain.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        global current_index
        if interaction.user.id in chain:
            idx = chain.index(interaction.user.id)
            chain.remove(interaction.user.id)
            if idx <= current_index and current_index > 0:
                current_index -= 1
            await update_embed(interaction.message, interaction.guild)
            await interaction.response.send_message("You left the chain.", ephemeral=True)
        else:
            await interaction.response.send_message("You are not in the chain.", ephemeral=True)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.blurple)
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        global current_index, reminder_task

        if not chain_active:
            await interaction.response.send_message("Chain hasn’t started yet.", ephemeral=True)
            return

        if interaction.user.id != chain[current_index]:
            await interaction.response.send_message("It’s not your turn.", ephemeral=True)
            return

        await interaction.response.defer()

        if reminder_task:
            reminder_task.cancel()

        current_index = (current_index + 1) % len(chain)

        next_user = interaction.guild.get_member(chain[current_index])
        next_next = interaction.guild.get_member(chain[(current_index + 1) % len(chain)])

        await interaction.channel.send(f"🔔 {next_user.mention} it’s your turn!")
        if next_next:
            await interaction.channel.send(f"👀 {next_next.mention} you’re next")

        reminder_task = asyncio.create_task(reminder_loop(interaction.channel, interaction.guild))

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.gray)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        global current_index, reminder_task

        if not is_leader_member(interaction.user):
            await interaction.response.send_message("Leader only.", ephemeral=True)
            return

        if not chain_active or not chain:
            await interaction.response.send_message("Chain is not active.", ephemeral=True)
            return

        await interaction.response.defer()

        if reminder_task:
            reminder_task.cancel()

        current_index = (current_index + 1) % len(chain)
        user = interaction.guild.get_member(chain[current_index])

        await interaction.channel.send(f"⏭ Skipped. {user.mention} it’s now your turn!")
        reminder_task = asyncio.create_task(reminder_loop(interaction.channel, interaction.guild))

# ---------- Commands ----------
@bot.command()
@commands.check(is_leader)
async def startchain(ctx):
    global chain, current_index, chain_active, chain_message_id, chain_view

    chain.clear()
    current_index = 0
    chain_active = False

    embed = discord.Embed(
        title="Torn Chain – Join Phase",
        description="Click **Participate** to join.\nLeader will start the chain.",
        color=0x00ff00
    )

    chain_view = ChainView()
    msg = await ctx.send(embed=embed, view=chain_view)
    chain_message_id = msg.id
    await msg.pin()

@bot.command()
@commands.check(is_leader)
async def beginchain(ctx):
    global chain_active, reminder_task

    if not chain:
        await ctx.send("No participants.")
        return

    chain_active = True
    first = ctx.guild.get_member(chain[0])
    await ctx.send(f"🔔 {first.mention} it’s your turn!")
    reminder_task = asyncio.create_task(reminder_loop(ctx.channel, ctx.guild))

@bot.command()
@commands.check(is_leader)
async def skip(ctx):
    global current_index, reminder_task

    if not chain_active or not chain:
        await ctx.send("Chain is not active.")
        return

    if reminder_task:
        reminder_task.cancel()

    current_index = (current_index + 1) % len(chain)
    user = ctx.guild.get_member(chain[current_index])
    await ctx.send(f"⏭ Skipped. {user.mention} it’s now your turn!")
    reminder_task = asyncio.create_task(reminder_loop(ctx.channel, ctx.guild))

@bot.command()
@commands.check(is_leader)
async def clearchain(ctx, limit: int = 50):
    def check(m):
        return m.author == bot.user and m.id != chain_message_id

    await ctx.channel.purge(limit=limit, check=check)
    await ctx.send("Bot messages cleared.", delete_after=5)

@bot.command()
@commands.check(is_leader)
async def stopchain(ctx):
    global chain_active, chain, reminder_task, chain_message_id

    chain_active = False
    chain.clear()

    if reminder_task:
        reminder_task.cancel()

    if chain_message_id:
        try:
            msg = await ctx.channel.fetch_message(chain_message_id)
            await msg.unpin()
            await msg.delete()
        except:
            pass

    chain_message_id = None
    await ctx.send("Chain stopped.")

@bot.command()
async def showqueue(ctx):
    if not chain:
        await ctx.send("Chain is empty.")
        return

    text = ""
    for i, uid in enumerate(chain):
        user = ctx.guild.get_member(uid)
        if not user:
            continue
        if i == current_index and chain_active:
            text += f"➡️ **{user.display_name}** (current)\n"
        else:
            text += f"{user.display_name}\n"

    embed = discord.Embed(title="Current Chain", description=text, color=0x00ff00)
    await ctx.send(embed=embed)

# ---------- Ready / Persistence ----------
@bot.event
async def on_ready():
    global chain_view
    chain_view = ChainView()
    bot.add_view(chain_view)
    print(f"Logged in as {bot.user}")

# ---------- Run ----------
bot.run(os.getenv("DISCORD_TOKEN"))
