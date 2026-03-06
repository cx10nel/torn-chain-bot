import discord
from discord.ext import commands, tasks
import asyncio
import time

TOKEN = "YOUR_TOKEN"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

queue = []
chain_message = None
chain_active = False
chain_start = None

TURN_TIME = 240
SKIP_BUFFER = 60


def progress_bar(seconds_left):

    total = TURN_TIME
    length = 20

    filled = int((seconds_left / total) * length)
    return "🟩" * filled + "⬜" * (length - filled)


def build_embed():

    if not chain_active:
        title = "Chain Inactive"
        desc = "Start a chain with !startchain"
        return discord.Embed(title=title, description=desc, color=0x808080)

    elapsed = int(time.time() - chain_start)
    remaining = max(0, TURN_TIME - elapsed)

    bar = progress_bar(remaining)

    embed = discord.Embed(
        title="🔥 Torn Chain Manager",
        color=0x00ff88
    )

    embed.add_field(
        name="⏳ Time Remaining",
        value=f"{remaining}s\n{bar}",
        inline=False
    )

    if queue:
        embed.add_field(
            name="🎯 Current Hitter",
            value=queue[0],
            inline=False
        )
    else:
        embed.add_field(
            name="🎯 Current Hitter",
            value="No one yet",
            inline=False
        )

    if len(queue) > 1:
        embed.add_field(
            name="➡️ Next",
            value=queue[1],
            inline=False
        )

    if queue:
        q = "\n".join(f"{i+1}. {user}" for i, user in enumerate(queue))
    else:
        q = "Queue empty"

    embed.add_field(
        name="📋 Queue",
        value=q,
        inline=False
    )

    embed.set_footer(text="Press DONE after your hit")

    return embed


class ChainButtons(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Join", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = interaction.user.display_name

        if user not in queue:
            queue.append(user)

        await interaction.response.defer()
        await update_panel()

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = interaction.user.display_name

        if user in queue:
            queue.remove(user)

        await interaction.response.defer()
        await update_panel()

    @discord.ui.button(label="Done", style=discord.ButtonStyle.blurple)
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):

        global chain_start

        user = interaction.user.display_name

        if queue and queue[0] == user:

            queue.pop(0)
            chain_start = time.time()

        await interaction.response.defer()
        await update_panel()

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.gray)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):

        global chain_start

        if queue:
            queue.pop(0)

        chain_start = time.time()

        await interaction.response.defer()
        await update_panel()


async def update_panel():

    if chain_message:

        embed = build_embed()

        try:
            await chain_message.edit(embed=embed)
        except:
            pass


@tasks.loop(seconds=5)
async def timer_loop():

    if chain_active:
        await update_panel()


@bot.command()
async def startchain(ctx):

    global chain_active
    global chain_start
    global chain_message

    chain_active = True
    chain_start = time.time()

    embed = build_embed()

    view = ChainButtons()

    chain_message = await ctx.send(embed=embed, view=view)

    if not timer_loop.is_running():
        timer_loop.start()


@bot.command()
async def queue(ctx):

    if not queue:
        await ctx.send("Queue empty")
        return

    q = "\n".join(f"{i+1}. {user}" for i, user in enumerate(queue))

    await ctx.send(f"**Current Queue**\n{q}")


@bot.command()
async def chainbuttons(ctx):

    view = ChainButtons()

    await ctx.send("Chain buttons:", view=view)


@bot.command()
async def clearchain(ctx):

    async for msg in ctx.channel.history(limit=100):

        if msg.author == bot.user:
            if chain_message and msg.id != chain_message.id:
                await msg.delete()

        if msg.content.startswith("!"):
            try:
                await msg.delete()
            except:
                pass

    await ctx.send("Chain cleaned.")


bot.run(TOKEN)
