import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

chain = []
chain_message_id = None
chain_active = False
bot_messages = []


def is_admin(member):
    return member.guild_permissions.administrator


class ChainView(discord.ui.View):
    def __init__(self, active=True):
        super().__init__(timeout=None)
        self.active = active

        for item in self.children:
            item.disabled = not active

    @discord.ui.button(label="Participating", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not chain_active:
            await interaction.response.send_message(
                "The chain is not active.", ephemeral=True
            )
            return

        if interaction.user in chain:
            await interaction.response.send_message(
                "You're already in the chain.", ephemeral=True
            )
            return

        chain.append(interaction.user)
        await update_chain(interaction)
        await interaction.response.send_message("Added to the chain.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in chain:
            await interaction.response.send_message(
                "You're not in the chain.", ephemeral=True
            )
            return

        chain.remove(interaction.user)
        await update_chain(interaction)
        await interaction.response.send_message("Removed from the chain.", ephemeral=True)

    @discord.ui.button(label="Done", style=discord.ButtonStyle.blurple)
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not chain_active:
            return

        if not chain or interaction.user != chain[0]:
            await interaction.response.send_message(
                "It's not your turn.", ephemeral=True
            )
            return

        finished = chain.pop(0)
        chain.append(finished)

        await update_chain(interaction, ping_next=True)
        await interaction.response.send_message("Turn complete!", ephemeral=True)


async def update_chain(interaction, ping_next=False):
    global chain_message_id

    channel = interaction.channel

    if not chain:
        description = "*No one is currently participating.*"
    else:
        description = ""
        for i, user in enumerate(chain):
            if i == 0:
                description += f"**➡️ {user.mention} (Your turn)**\n"
            else:
                description += f"{i+1}. {user.mention}\n"

    embed = discord.Embed(
        title="🔗 Torn Chain Organizer",
        description=description,
        color=discord.Color.red()
    )

    view = ChainView(active=chain_active)

    if chain_message_id:
        msg = await channel.fetch_message(chain_message_id)
        await msg.edit(embed=embed, view=view)
    else:
        msg = await channel.send(embed=embed, view=view)
        chain_message_id = msg.id
        bot_messages.append(msg.id)

    if ping_next and chain:
        ping = await channel.send(f"🔥 {chain[0].mention}, it's your turn!")
        bot_messages.append(ping.id)


@bot.command()
@commands.has_permissions(administrator=True)
async def startchain(ctx):
    global chain, chain_message_id, chain_active

    chain.clear()
    chain_message_id = None
    chain_active = True

    msg = await ctx.send(
        embed=discord.Embed(
            title="🔗 Torn Chain Organizer",
            description="Click **Participating** to join the chain.",
            color=discord.Color.red()
        ),
        view=ChainView(active=True)
    )

    chain_message_id = msg.id
    bot_messages.append(msg.id)


@bot.command()
@commands.has_permissions(administrator=True)
async def stopchain(ctx):
    global chain_active

    chain_active = False
    await update_chain(ctx)
    await ctx.send("🛑 The chain has been stopped.")


@bot.command()
@commands.has_permissions(administrator=True)
async def clearchain(ctx):
    global chain, chain_message_id, bot_messages, chain_active

    for msg_id in bot_messages:
        try:
            msg = await ctx.channel.fetch_message(msg_id)
            await msg.delete()
        except:
            pass

    chain.clear()
    chain_message_id = None
    bot_messages.clear()
    chain_active = False

    await ctx.send("🧹 Chain messages cleared.")


import os
bot.run(os.getenv("DISCORD_TOKEN"))
