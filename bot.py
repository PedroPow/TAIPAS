import os
import json
from datetime import datetime
from typing import Optional
import aiohttp
import asyncio
import io
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from dotenv import load_dotenv
load_dotenv()

# ================= CONFIGURAÇÕES =================
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("❌ TOKEN não definido nas variáveis de ambiente")

GUILD_ID = 1343398652336537654
CATEGORY_TICKETS = 1343398652349255757
CANAL_SETS = 1450001795572039721
CANAL_BOTAO_FIXO = 1343398652349255758
LOG_CHANNEL_ID = 1450001931278745640

CARGO_INICIAL = 1345435302285545652
ALLOWED_APPROVERS = [1449985109116715008]
APPROVED_ROLE_ID = 1343645401051431017

CARGO_MAP = {
    "[❯] Soldado de 1º Classe PM": 1343408322774175785,
    "[❯❯] Cabo PM": 1343408303417331772,
    "[❯❯❯] 3º Sargento PM": 1343404402219814932,
    "[❯ ❯❯❯] 2º Sargento PM": 1343408106457272462,
    "[❯❯ ❯❯❯] 1º Sargento PM": 1343408155161264158,
    "[△] Sub-Tenente PM": 1343727303795933184,
    "[✯] Aspirante a Oficial PM": 1343648749381091570,
    "[✧] 2º Tenente PM": 1343419697294479471,
    "[✧✧] 1º Tenente PM": 1343408376302014495,
    "[✧✧✧] Capitão PM": 1343404318946103346,
    "[✵✧✧] Major PM": 1343401976523784253,
    "[✵✵✧] Tenente Coronel PM": 1343401212417937468,
}

QUEBRADA_MAP = {
    "1° BPCHOq ROTA": 1343645401051431017,
}

QUEBRADAS = list(QUEBRADA_MAP.keys())
CARGOS = list(CARGO_MAP.keys())

DATA_FOLDER = "data"
BLACKLIST_FILE = os.path.join(DATA_FOLDER, "blacklist.json")
PENDING_FILE = os.path.join(DATA_FOLDER, "pending_sets.json")

LOGO_PATH = "/mnt/data/IMAGEM_NORMAL_NATAL.png"
LOGO_FILENAME = "logo.png"

NICK_FORMAT = "{id} | {vulgo}"

# ================= BOT =================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

os.makedirs(DATA_FOLDER, exist_ok=True)

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2, ensure_ascii=False)
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

blacklist = load_json(BLACKLIST_FILE, {"ids": []})
pending_sets = load_json(PENDING_FILE, {"sets": []})

def is_approver(member: discord.Member) -> bool:
    return (
        any(r.id in ALLOWED_APPROVERS for r in member.roles)
        or member.guild_permissions.administrator
    )

def make_embed(title, desc="", color=0x00FF38):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="Sistema de SET • PCC Zona Leste")
    return e

class FixedButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📑 Iniciar SET",
        style=discord.ButtonStyle.primary,
        custom_id="iniciar_set"
    )
    async def iniciar(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id in blacklist.get("ids", []):
            return await interaction.response.send_message(
                "❌ Você está na blacklist.",
                ephemeral=True
            )

        categoria = interaction.guild.get_channel(CATEGORY_TICKETS)
        canal = await interaction.guild.create_text_channel(
            name=f"set-{interaction.user.name}",
            category=categoria
        )

        await canal.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await canal.send(
            embed=make_embed(
                "📑 SET INICIADO",
                "Selecione sua **quebrada** e **patente** para continuar."
            )
        )

        await interaction.response.send_message(
            f"✅ Ticket criado: {canal.mention}",
            ephemeral=True
        )


# ================= MODAL =================
class ModalSetFinal(Modal, title="📑 Finalizar SET"):
    nome = TextInput(label="Nome Completo")
    vulgo = TextInput(label="Nome de Guerra")
    idd = TextInput(label="ID")
    numerada = TextInput(label="Numerada", required=False)
    responsavel = TextInput(label="Responsável", required=False)

    def __init__(self, user, ticket, quebrada, cargo):
        super().__init__()
        self.user = user
        self.ticket = ticket
        self.quebrada = quebrada
        self.cargo = cargo

    async def on_submit(self, interaction: discord.Interaction):
        data = {
            "user_id": self.user.id,
            "ticket_channel_id": self.ticket.id,
            "nome": self.nome.value,
            "NDG": self.vulgo.value,
            "idd": self.idd.value,
            "numerada": self.numerada.value,
            "RESPONSAVEL": self.responsavel.value,
            "BTA": self.quebrada,
            "PATENTE": self.cargo,
            "timestamp": datetime.utcnow().isoformat()
        }

        embed = make_embed("☯️ NOVO SET RECEBIDO")
        embed.add_field(name="Nome", value=data["nome"], inline=False)
        embed.add_field(name="Vulgo", value=data["NDG"], inline=False)
        embed.add_field(name="ID", value=data["idd"], inline=False)
        embed.add_field(name="Numerada", value=data["numerada"] or "—", inline=False)
        embed.add_field(name="Responsável", value=data["RESPONSAVEL"] or "—", inline=False)
        embed.add_field(name="BTA", value=data["BTA"], inline=True)
        embed.add_field(name="Patente", value=data["PATENTE"], inline=True)

        staff = interaction.guild.get_channel(CANAL_SETS)
        view = ApproveDenyView(data)
        msg = await staff.send(embed=embed, view=view)

        data["staff_message_id"] = msg.id
        pending_sets["sets"].append(data)
        save_json(PENDING_FILE, pending_sets)

        await interaction.response.send_message("📨 SET enviado para análise.", ephemeral=True)

# ================= VIEW APROVAÇÃO =================
class ApproveDenyView(View):
    def __init__(self, data):
        super().__init__(timeout=None)
        self.data = data

    @discord.ui.button(label="✔️ ACEITAR", style=discord.ButtonStyle.green)
    async def aceitar(self, interaction: discord.Interaction, button: Button):
        if not is_approver(interaction.user):
            return await interaction.response.send_message("🔒 Sem permissão.", ephemeral=True)
        await POS_SETAGEM(interaction, self.data)

async def POS_SETAGEM(interaction: discord.Interaction, data: dict):
    guild = interaction.guild

    member = guild.get_member(data["user_id"])
    if member is None:
        member = await guild.fetch_member(data["user_id"])

    await member.edit(
        nick=NICK_FORMAT.format(id=data["idd"], vulgo=data["NDG"]),
        reason="SET aprovado"
    )

    for role_id in (
        APPROVED_ROLE_ID,
        CARGO_MAP.get(data["PATENTE"]),
        QUEBRADA_MAP.get(data["BTA"]),
    ):
        role = guild.get_role(role_id)
        if role:
            await member.add_roles(role)

    log = guild.get_channel(LOG_CHANNEL_ID)
    if log:
        await log.send(embed=make_embed("🟢 SET APROVADO", member.mention))

    ticket = guild.get_channel(data["ticket_channel_id"])
    if ticket:
        await ticket.delete(reason="SET aprovado")

    await interaction.response.send_message("✔️ SET aprovado com sucesso.", ephemeral=True)

# ================= SLASH COMMANDS =================
@bot.tree.command(name="mensagem", description="Envie uma mensagem pelo bot", guild=discord.Object(id=GUILD_ID))
async def mensagem(interaction: discord.Interaction):
    # Permissões: mantenha seus role ids conforme necessário
    allowed_role_ids = [
        1364016462154563614,  # PRESIDENTE
        1364016541330575451,  # VICE PRESIDENTE
        1389710649390534717,  # GOVERNADOR
        1376730670910537788   # DEV
    ]
    if not any(discord.utils.get(interaction.user.roles, id=role_id) for role_id in allowed_role_ids):
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    class MensagemModal(discord.ui.Modal, title="📨 Enviar Mensagem"):
        conteudo = discord.ui.TextInput(
            label="Conteúdo da Mensagem",
            style=discord.TextStyle.paragraph,
            placeholder="Escreva a mensagem com quebras de linha, emojis etc.",
            max_length=2000
        )

        async def on_submit(self, interaction_modal: discord.Interaction):
            await interaction_modal.response.send_message("⏳ Enviando mensagem...", ephemeral=True)
            sent_msg = await interaction.channel.send(self.conteudo.value)

            await interaction_modal.followup.send(
                "📎 Se desejar, **responda à mensagem enviada** com anexos (imagens/vídeos) **em até 5 minutos**.",
                ephemeral=True
            )

            def check(m):
                return (
                    m.reference and
                    m.reference.message_id == sent_msg.id and
                    m.author == interaction_modal.user and
                    m.channel == interaction_modal.channel
                )

            try:
                reply_msg = await bot.wait_for("message", timeout=300.0, check=check)

                arquivos = []
                async with aiohttp.ClientSession() as session:
                    for attachment in reply_msg.attachments:
                        async with session.get(attachment.url) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                arquivos.append(discord.File(fp=io.BytesIO(data), filename=attachment.filename))

                try:
                    await sent_msg.delete()
                except discord.Forbidden:
                    pass
                try:
                    await reply_msg.delete()
                except discord.Forbidden:
                    pass

                await interaction.channel.send(content=self.conteudo.value, files=arquivos)

            except asyncio.TimeoutError:
                pass

    await interaction.response.send_modal(MensagemModal())


@bot.tree.command(name="ban", description="Banir um usuário")
@app_commands.checks.has_permissions(ban_members=True)
async def slash_ban(interaction: discord.Interaction, membro: discord.Member, motivo: str = "Sem motivo"):
    await membro.ban(reason=motivo)
    await interaction.response.send_message(f"🔨 {membro} banido.", ephemeral=True)

@bot.tree.command(name="adv", description="Advertir um usuário")
@app_commands.checks.has_permissions(manage_guild=True)
async def slash_adv(interaction: discord.Interaction, membro: discord.Member, motivo: str):
    embed = discord.Embed(title="⚠️ Advertência", color=0xFFA500, timestamp=datetime.utcnow())
    embed.add_field(name="Usuário", value=membro.mention)
    embed.add_field(name="Staff", value=interaction.user.mention)
    embed.add_field(name="Motivo", value=motivo, inline=False)

    log = interaction.guild.get_channel(LOG_CHANNEL_ID)
    if log:
        await log.send(embed=embed)

    await interaction.response.send_message("⚠️ Advertência registrada.", ephemeral=True)

@bot.tree.command(name="clearall", description="Apagar mensagens")
@app_commands.checks.has_permissions(manage_messages=True)
async def slash_clearall(interaction: discord.Interaction, quantidade: int):
    if not 1 <= quantidade <= 100:
        return await interaction.response.send_message("Use 1 a 100.", ephemeral=True)
    await interaction.channel.purge(limit=quantidade)
    await interaction.response.send_message(f"🧹 {quantidade} mensagens apagadas.", ephemeral=True)

# ================= START =================
@bot.event
async def on_ready():
    bot.add_view(FixedButtonView())

    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Erro ao sincronizar slash: {e}")

    print(f"🤖 Bot online como {bot.user}")


if __name__ == "__main__":
    bot.run(TOKEN)
