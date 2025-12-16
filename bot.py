# ================= IMPORTS =================
import os
import json
import asyncio
import aiohttp
import io
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from dotenv import load_dotenv

load_dotenv()

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("❌ TOKEN não definido")

GUILD_ID = 1343398652336537654

CATEGORY_TICKETS = 1343398652349255757
CANAL_BOTAO_FIXO = 1343398652349255758
CANAL_SETS = 1450001795572039721
LOG_CHANNEL_ID = 1450001931278745640

APPROVED_ROLE_ID = 1343645401051431017
ALLOWED_APPROVERS = [1449985109116715008]

# ADV ROLES
ADV_VERBAL = 1343788657760534619
ADV_1 = 1343647931743469620
ADV_2 = 1343648148861489247
ADV_3 = 1343648181174665228

ADV_ORDER = [ADV_VERBAL, ADV_1, ADV_2, ADV_3]

CARGO_MAP = {
    "soldado de 2° classe PM": 1343644654729560166,
    "❯ Soldado de 1º Classe PM": 1343408322774175785,
    "❯❯ Cabo PM": 1343408303417331772,
    "❯❯❯ 3º Sargento PM": 1343404402219814932,
    "❯ ❯❯❯ 2º Sargento PM": 1343408106457272462,
    "❯❯ ❯❯❯ 1º Sargento PM": 1343408155161264158,
    "△ Sub-Tenente PM": 1343727303795933184,
    "✯ Aspirante a Oficial PM": 1343648749381091570,
    "✧ 2º Tenente PM": 1343419697294479471,
    "✧✧ 1º Tenente PM": 1343408376302014495,
    "✧✧✧ Capitão PM": 1343404318946103346,
    "✵✧✧ Major PM": 1343401976523784253, 
    "✵✵✧ Tenente Coronel PM": 1343401212417937468, 
}

BATALHAO_MAP = {
    "1° BPCHOq ROTA": 1343645401051431017
}

NICK_FORMAT = "{id} | {vulgo}"

DATA = "data"
os.makedirs(DATA, exist_ok=True)

PENDING_FILE = f"{DATA}/pending.json"
HISTORY_FILE = f"{DATA}/history.json"
BLACKLIST_FILE = f"{DATA}/blacklist.json"

# ================= BOT =================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= UTILS =================
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

pending = load_json(PENDING_FILE, {})
history = load_json(HISTORY_FILE, {})
blacklist = load_json(BLACKLIST_FILE, {"ids": []})

def is_approver(member):
    return any(r.id in ALLOWED_APPROVERS for r in member.roles) or member.guild_permissions.administrator

def embed(title, desc="", color=0x00ff38):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="Sistema de SET • PCC Zona Leste")
    return e

# ================= SET FLOW =================
class FixedButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📑 Iniciar SET", style=discord.ButtonStyle.primary, custom_id="start_set")
    async def start(self, interaction: discord.Interaction, button: Button):

        if str(interaction.user.id) in pending:
            return await interaction.response.send_message("❌ Você já possui um SET em andamento.", ephemeral=True)

        category = interaction.guild.get_channel(CATEGORY_TICKETS)
        channel = await interaction.guild.create_text_channel(
            f"set-{interaction.user.name}", category=category
        )

        pending[str(interaction.user.id)] = {
            "ticket": channel.id
        }
        save_json(PENDING_FILE, pending)

        await channel.send(
            embed=embed("SET INICIADO", "Selecione o **BATALHÃO**"),
            view=BatalhaoView(interaction.user)
        )

        await interaction.response.send_message("✅ Ticket criado.", ephemeral=True)

class BatalhaoView(View):
    def __init__(self, user):
        super().__init__()
        self.user = user

        self.add_item(
            Select(
                placeholder="Selecione o Batalhão",
                options=[discord.SelectOption(label=k) for k in BATALHAO_MAP],
                callback=self.select
            )
        )

    async def select(self, interaction):
        batalhao = interaction.data["values"][0]
        await interaction.response.edit_message(
            embed=embed("SET", "Selecione a **PATENTE**"),
            view=PatenteView(self.user, batalhao)
        )

class PatenteView(View):
    def __init__(self, user, batalhao):
        super().__init__()
        self.user = user
        self.batalhao = batalhao

        self.add_item(
            Select(
                placeholder="Selecione a Patente",
                options=[discord.SelectOption(label=k) for k in CARGO_MAP],
                callback=self.select
            )
        )

    async def select(self, interaction):
        patente = interaction.data["values"][0]
        await interaction.response.send_modal(
            SetModal(self.user, interaction.channel, self.batalhao, patente)
        )

class SetModal(Modal, title="Finalizar SET"):
    nome = TextInput(label="Nome Completo")
    vulgo = TextInput(label="Vulgo")
    idd = TextInput(label="ID")

    def __init__(self, user, ticket, batalhao, patente):
        super().__init__()
        self.user = user
        self.ticket = ticket
        self.batalhao = batalhao
        self.patente = patente

    async def on_submit(self, interaction):
        data = {
            "user": self.user.id,
            "ticket": self.ticket.id,
            "nome": self.nome.value,
            "vulgo": self.vulgo.value,
            "id": self.idd.value,
            "batalhao": self.batalhao,
            "patente": self.patente
        }

        ch = interaction.guild.get_channel(CANAL_SETS)
        await ch.send(embed=embed("NOVO SET", f"<@{self.user.id}>"), view=ApproveDenyView(data))
        await interaction.response.send_message("📨 SET enviado.", ephemeral=True)

class ApproveDenyView(View):
    def __init__(self, data):
        super().__init__(timeout=None)
        self.data = data

    @discord.ui.button(label="✔️ APROVAR", style=discord.ButtonStyle.green)
    async def approve(self, interaction, _):
        if not is_approver(interaction.user):
            return await interaction.response.send_message("Sem permissão.", ephemeral=True)

        guild = interaction.guild
        member = await guild.fetch_member(self.data["user"])

        await member.edit(nick=NICK_FORMAT.format(id=self.data["id"], vulgo=self.data["vulgo"]))
        await member.add_roles(
            guild.get_role(APPROVED_ROLE_ID),
            guild.get_role(CARGO_MAP[self.data["patente"]]),
            guild.get_role(BATALHAO_MAP[self.data["batalhao"]])
        )

        pending.pop(str(member.id), None)
        history.setdefault(str(member.id), []).append(self.data)
        save_json(PENDING_FILE, pending)
        save_json(HISTORY_FILE, history)

        await interaction.response.send_message("✔️ SET aprovado.", ephemeral=True)

    @discord.ui.button(label="❌ RECUSAR", style=discord.ButtonStyle.red)
    async def deny(self, interaction, _):
        pending.pop(str(self.data["user"]), None)
        save_json(PENDING_FILE, pending)
        await interaction.response.send_message("❌ SET recusado.", ephemeral=True)

# ================= ADV COMMAND =================
@bot.tree.command(name="adv", description="Aplicar advertência")
async def adv(interaction: discord.Interaction, membro: discord.Member):

    roles = [r.id for r in membro.roles]
    guild = interaction.guild

    for adv in ADV_ORDER:
        if adv in roles:
            guild_role = guild.get_role(adv)
            await membro.remove_roles(guild_role)

    for adv in ADV_ORDER:
        if adv not in roles:
            await membro.add_roles(guild.get_role(adv))
            if adv == ADV_3:
                await membro.ban(reason="Limite de advertências")
            break

    await interaction.response.send_message("⚠️ Advertência aplicada.", ephemeral=True)

# ================= SLASH: MENSAGEM =================
@bot.tree.command(name="mensagem", description="Envie uma mensagem pelo bot", guild=discord.Object(id=GUILD_ID))
async def mensagem(interaction: discord.Interaction):
    allowed = [1449985109116715008]
    if not any(r.id in allowed for r in interaction.user.roles):
        return await interaction.response.send_message("Sem permissão.", ephemeral=True)

    class MsgModal(Modal, title="Enviar Mensagem"):
        texto = TextInput(label="Mensagem", style=discord.TextStyle.paragraph)

        async def on_submit(self, i):
            await i.channel.send(self.texto.value)
            await i.response.send_message("✅ Enviado.", ephemeral=True)

    await interaction.response.send_modal(MsgModal())

# ================= READY =================
@bot.event
async def on_ready():
    bot.add_view(FixedButtonView())
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print("🤖 Bot online")

bot.run(TOKEN)
