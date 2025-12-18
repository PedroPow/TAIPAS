import discord
import aiohttp
import asyncio
import io
import os
from discord.ext import commands
from discord.ui import Modal, TextInput

# ============================
#   CONFIGURAÇÕES DO SERVIDOR
# ============================
GUILD_ID = 1343398652336537654

VERIFY_CHANNEL_ID = 1343398652349255758
LOG_CHANNEL_ID = 1450001931278745640

ROLE_VERIFY_ID = 1343645401051431017
ROLE_AUTOROLE_ID = 1345435302285545652
ADMIN_ROLE_ID = 1449998328334123208

PAINEL_CHANNEL_ID = 1450968994076033115

# Advertências
ID_CARGO_ADV1 = 1343788657760534619
ID_CARGO_ADV2 = 1343647931743469620
ID_CARGO_ADV3 = 1343648148861489247
ID_CARGO_BANIDO = 1343648181174665228

CARGOS_AUTORIZADOS = [1449985109116715008]

# ============================
#         BOT
# ============================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv("TOKEN")

bot._ready_sent = False

# ============================
#        LOGS
# ============================
async def enviar_log_embed(guild, embed):
    if guild:
        canal = guild.get_channel(LOG_CHANNEL_ID)
        if canal:
            await canal.send(embed=embed)

async def enviar_log(guild, titulo, descricao):
    if guild:
        canal = guild.get_channel(LOG_CHANNEL_ID)
        if canal:
            embed = discord.Embed(title=titulo, description=descricao)
            await canal.send(embed=embed)

# ============================
#      PERMISSÃO
# ============================
def has_authorized_role(member):
    return any(r.id in CARGOS_AUTORIZADOS for r in member.roles)

async def require_authorized(interaction):
    if not has_authorized_role(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return False
    return True

# ============================
#      VERIFY BUTTON
# ============================
class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Verificar", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify(self, interaction, button):
        role = interaction.guild.get_role(ROLE_VERIFY_ID)
        if role in interaction.user.roles:
            return await interaction.response.send_message("Já verificado.", ephemeral=True)
        await interaction.user.add_roles(role)
        await interaction.response.send_message("Verificado!", ephemeral=True)

# ============================
#        AUTOROLE
# ============================
@bot.event
async def on_member_join(member):
    role = member.guild.get_role(ROLE_AUTOROLE_ID)
    if role:
        await member.add_roles(role)

# ============================
#        CLEARALL
# ============================
@bot.tree.command(name="clearall", guild=discord.Object(id=GUILD_ID))
async def clearall(interaction):
    if not await require_authorized(interaction):
        return
    await interaction.response.send_message("🧹 Limpando...", ephemeral=True)
    await interaction.channel.purge()

# ============================
#        MENSAGEM
# ============================
class MensagemModal(Modal, title="Mensagem"):
    conteudo = TextInput(label="Mensagem", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction):
        if not has_authorized_role(interaction.user):
            return
        await interaction.channel.send(self.conteudo.value)
        await interaction.response.send_message("Enviado.", ephemeral=True)

@bot.tree.command(name="mensagem", guild=discord.Object(id=GUILD_ID))
async def mensagem(interaction):
    if await require_authorized(interaction):
        await interaction.response.send_modal(MensagemModal())

# ============================
#        ADV (CORRIGIDO)
# ============================
@bot.tree.command(name="adv", description="Advertir membro", guild=discord.Object(id=GUILD_ID))
async def adv(interaction, membro: discord.Member, motivo: str):
    if not await require_authorized(interaction):
        return

    adv1 = interaction.guild.get_role(ID_CARGO_ADV1)
    adv2 = interaction.guild.get_role(ID_CARGO_ADV2)
    adv3 = interaction.guild.get_role(ID_CARGO_ADV3)
    banido = interaction.guild.get_role(ID_CARGO_BANIDO)

    if banido in membro.roles:
        return await interaction.response.send_message("Já banido.", ephemeral=True)

    if adv3 in membro.roles:
        await membro.remove_roles(adv3)
        await membro.add_roles(banido)
        msg = "🚫 BANIDO"
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
#        BAN
# ============================
@bot.tree.command(name="ban", guild=discord.Object(id=GUILD_ID))
async def ban(interaction, membro: discord.Member, motivo: str):
    if not await require_authorized(interaction):
        return
    await membro.ban(reason=motivo)
    await interaction.response.send_message("Banido.", ephemeral=True)

# ============================
#        READY (FIX)
# ============================
@bot.event
async def on_ready():
    if bot._ready_sent:
        return
    bot._ready_sent = True

    print(f"🔥 Conectado como {bot.user}")

    guild = discord.Object(id=GUILD_ID)

    # 🔥 FIX PRINCIPAL
    bot.tree.clear_commands(guild=guild)
    synced = await bot.tree.sync(guild=guild)

    print("Slash sincronizados:", [c.name for c in synced])

# ============================
#        RUN
# ============================
bot.run(TOKEN)
