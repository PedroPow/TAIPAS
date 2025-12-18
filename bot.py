import discord
import aiohttp
import asyncio
import io
import os
from discord.ext import commands
from discord.ui import Modal, TextInput

# ============================
#   CONFIGURAÇÕES
# ============================
GUILD_ID = 1343398652336537654

VERIFY_CHANNEL_ID = 1343398652349255758
LOG_CHANNEL_ID = 1450001931278745640
PAINEL_CHANNEL_ID = 1450968994076033115

ROLE_VERIFY_ID = 1343645401051431017
ROLE_AUTOROLE_ID = 1345435302285545652
ADMIN_ROLE_ID = 1449998328334123208

# Advertências
ID_CARGO_ADV1 = 1343788657760534619
ID_CARGO_ADV2 = 1343647931743469620
ID_CARGO_ADV3 = 1343648148861489247
ID_CARGO_BANIDO = 1343648181174665228

CARGOS_AUTORIZADOS = [1449985109116715008]

# ============================
# BOT
# ============================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv("TOKEN")

bot._ready_sent = False

# ============================
# HELPERS
# ============================
def has_authorized_role(member: discord.Member):
    return any(r.id in CARGOS_AUTORIZADOS for r in member.roles)

async def require_authorized(interaction: discord.Interaction):
    if not has_authorized_role(interaction.user):
        await interaction.response.send_message(
            "❌ Você não tem permissão.", ephemeral=True
        )
        return False
    return True

async def enviar_log_embed(guild, embed):
    canal = guild.get_channel(LOG_CHANNEL_ID)
    if canal:
        await canal.send(embed=embed)

# ============================
# VERIFY BUTTON
# ============================
class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Verificar", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, _):
        role = interaction.guild.get_role(ROLE_VERIFY_ID)
        if role in interaction.user.roles:
            return await interaction.response.send_message(
                "Você já está verificado.", ephemeral=True
            )

        await interaction.user.add_roles(role)
        await interaction.response.send_message(
            "🎉 Verificado com sucesso!", ephemeral=True
        )

# ============================
# AUTOROLE
# ============================
@bot.event
async def on_member_join(member):
    role = member.guild.get_role(ROLE_AUTOROLE_ID)
    if role:
        await member.add_roles(role)

# ============================
# /clearall
# ============================
@bot.tree.command(name="clearall", description="Limpa o canal atual")
async def clearall(interaction: discord.Interaction):
    if not await require_authorized(interaction):
        return

    await interaction.response.send_message("🧹 Limpando...", ephemeral=True)
    await interaction.channel.purge()
    await interaction.channel.send("✅ Canal limpo.")

# ============================
# MODAL /mensagem
# ============================
class MensagemModal(Modal, title="Enviar mensagem"):
    conteudo = TextInput(label="Mensagem", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction):
        await interaction.channel.send(self.conteudo.value)
        await interaction.response.send_message("✅ Enviado.", ephemeral=True)

@bot.tree.command(name="mensagem", description="Enviar mensagem como bot")
async def mensagem(interaction: discord.Interaction):
    if not await require_authorized(interaction):
        return
    await interaction.response.send_modal(MensagemModal())

# ============================
# /adv
# ============================
@bot.tree.command(name="adv", description="Aplicar advertência")
async def adv(interaction: discord.Interaction, membro: discord.Member, motivo: str):
    if not await require_authorized(interaction):
        return

    guild = interaction.guild
    adv1 = guild.get_role(ID_CARGO_ADV1)
    adv2 = guild.get_role(ID_CARGO_ADV2)
    adv3 = guild.get_role(ID_CARGO_ADV3)
    banido = guild.get_role(ID_CARGO_BANIDO)

    if banido in membro.roles:
        return await interaction.response.send_message(
            "🚫 Já está banido.", ephemeral=True
        )

    if adv3 in membro.roles:
        await membro.remove_roles(adv3)
        await membro.add_roles(banido)
        msg = "🚫 BANIDO (4ª advertência)"
    elif adv2 in membro.roles:
        await membro.remove_roles(adv2)
        await membro.add_roles(adv3)
        msg = "⚠ 3ª advertência"
    elif adv1 in membro.roles:
        await membro.remove_roles(adv1)
        await membro.add_roles(adv2)
        msg = "⚠ 2ª advertência"
    else:
        await membro.add_roles(adv1)
        msg = "⚠ 1ª advertência"

    await interaction.response.send_message(msg, ephemeral=True)

# ============================
# ON_READY
# ============================
@bot.event
async def on_ready():
    if bot._ready_sent:
        return
    bot._ready_sent = True

    print(f"🔥 Conectado como {bot.user}")

    # 🔥 SYNC GLOBAL (SEM GUILD)
    synced = await bot.tree.sync()
    print(f"Slash sincronizados: {[c.name for c in synced]}")

    guild = bot.get_guild(GUILD_ID)
    if guild:
        canal = guild.get_channel(VERIFY_CHANNEL_ID)
        if canal:
            await canal.purge(limit=5)
            await canal.send(
                embed=discord.Embed(
                    title="Verificação",
                    description="Clique para se verificar"
                ),
                view=VerifyButton()
            )

# ============================
# RUN
# ============================
if not TOKEN:
    print("❌ TOKEN não definido")
else:
    bot.run(TOKEN)
