from unicodedata import name
import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from discord import Embed
import asyncio
import os
import sys

sys.modules['audioop'] = None

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= CONFIGURAÇÃO =================

TOKEN = os.getenv("TOKEN")

CANALETA_SOLICITAR_SET_ID = 1343398652349255758
CARGO_NOVATO_ID = 1345435302285545652
CATEGORIA_TICKET_ID = 1343398652349255757

COMPANHIAS_CHANNEL = {
    "1° BPCHQ ROTA": 1450001795572039721,
}

CARGOS_COMPANHIA = {
    "1° BPCHQ ROTA": 1343645401051431017,
}

PATENTES_ESPECIALIZADAS = {
    "1° BPCHQ ROTA": {
        "[❯] Soldado de 1º Classe PM": 1362602865285140490,
        "[❯❯] Cabo PM": 1362602838928134345,
        "[❯❯❯] 3º Sargento PM": 1362602768732393503,
        "[❯ ❯❯❯] 2º Sargento PM": 1362602740160790599,
        "[❯❯ ❯❯❯] 1º Sargento PM": 1362602703707963484,
        "[△] Sub-Tenente PM": 1362602675312787526,
        "[✯] Aspirante a Oficial PM": 1362602649307844838,
        "[✧] 2º Tenente PM": 1362602616348999781,
        "[✧✧] 1º Tenente PM": 1362602576419360778,
        "[✧✧✧] Capitão PM": 1362602545897537768,
        "[✵✧✧] Major PM": 1362602512120549499,
        "[✵✵✧] Tenente Coronel PM": 1362602485092581586,
    }
}

# ================= ESTADO =================

solicitacoes_abertas = {}

# ================= FUNÇÕES =================

def get_patentes_para(companhia):
    return PATENTES_ESPECIALIZADAS.get(companhia)

# ================= VIEWS =================

class TicketView(View):
    @discord.ui.button(label="Solicitar Funcional", style=discord.ButtonStyle.secondary, custom_id="iniciar_pedido")
    async def abrir_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        user = interaction.user

        if user.id in solicitacoes_abertas:
            await interaction.response.send_message("⚠️ Você já possui um ticket aberto.", ephemeral=True)
            return

        category = guild.get_channel(CATEGORIA_TICKET_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        canal = await guild.create_text_channel(
            name=f"ticket-{user.name}",
            category=category,
            overwrites=overwrites
        )

        solicitacoes_abertas[user.id] = {
            "canal_id": canal.id
        }

        view = View(timeout=None)
        view.add_item(SelectCompanhia(user.id))

        await canal.send(f"{user.mention}, selecione sua companhia:", view=view)
        await interaction.response.send_message("🎟️ Ticket criado!", ephemeral=True)

class SelectCompanhia(Select):
    def __init__(self, user_id):
        self.user_id = user_id
        options = [discord.SelectOption(label=nome, value=nome) for nome in COMPANHIAS_CHANNEL]
        super().__init__(placeholder="Escolha sua companhia", options=options)

    async def callback(self, interaction: discord.Interaction):
        patentes = get_patentes_para(self.values[0])
        view = View(timeout=None)
        view.add_item(SelectPatente(self.user_id, self.values[0], patentes))
        await interaction.response.send_message(
            f"Companhia **{self.values[0]}** selecionada. Agora escolha a patente:",
            view=view,
            ephemeral=True
        )

class SelectPatente(Select):
    def __init__(self, user_id, companhia, patentes):
        self.user_id = user_id
        self.companhia = companhia
        self.patentes = patentes
        options = [discord.SelectOption(label=n, value=n) for n in patentes]
        super().__init__(placeholder="Escolha sua patente", options=options)

    async def callback(self, interaction: discord.Interaction):
        nome = self.values[0]
        await interaction.response.send_modal(
            DadosPessoaisModal(
                self.user_id,
                self.companhia,
                nome,
                self.patentes[nome],
                CARGOS_COMPANHIA[self.companhia]
            )
        )

class DadosPessoaisModal(Modal, title="Informe seus dados"):
    nome = TextInput(label="Nome Completo", required=True)
    passaporte = TextInput(label="Passaporte", required=True)

    def __init__(self, user_id, companhia, patente_nome, patente_id, companhia_id):
        super().__init__()
        self.user_id = user_id
        self.companhia = companhia
        self.patente_nome = patente_nome
        self.patente_id = patente_id
        self.companhia_id = companhia_id

    async def on_submit(self, interaction: discord.Interaction):
        solicitacoes_abertas[self.user_id] = {
            "canal_id": solicitacoes_abertas[self.user_id]["canal_id"],
            "patente_id": self.patente_id,
            "companhia_id": self.companhia_id,
            "nome": self.nome.value.strip(),
            "passaporte": self.passaporte.value.strip()
        }

        embed = Embed(
            title="Solicitação de SET",
            description=(
                f"**Nome:** {self.nome.value}\n"
                f"**Passaporte:** {self.passaporte.value}\n"
                f"**Companhia:** {self.companhia}\n"
                f"**Patente:** {self.patente_nome}"
            ),
            color=discord.Color.dark_gray()
        )

        canal_logs = bot.get_channel(COMPANHIAS_CHANNEL[self.companhia])
        await canal_logs.send(embed=embed, view=ConfirmarOuFecharView(self.user_id))
        await interaction.response.send_message("✅ Solicitação enviada.", ephemeral=True)

class ConfirmarOuFecharView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="✅ Confirmar SET", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: Button):
        dados = solicitacoes_abertas.pop(self.user_id, None)
        if not dados:
            await interaction.response.send_message("❌ Solicitação não encontrada.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        membro = interaction.guild.get_member(self.user_id)
        if not membro:
            return

        try:
            await membro.edit(nick=f"#{dados['passaporte']} | {dados['nome']}")
        except:
            pass

        novato = interaction.guild.get_role(CARGO_NOVATO_ID)
        if novato in membro.roles:
            await membro.remove_roles(novato)

        await membro.add_roles(
            interaction.guild.get_role(dados['patente_id']),
            interaction.guild.get_role(dados['companhia_id'])
        )

        canal = interaction.guild.get_channel(dados["canal_id"])
        if canal:
            await asyncio.sleep(3)
            await canal.delete()

    @discord.ui.button(label="❌ Fechar Solicitação", style=discord.ButtonStyle.danger)
    async def fechar(self, interaction: discord.Interaction, button: Button):
        dados = solicitacoes_abertas.pop(self.user_id, None)
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        if dados:
            canal = interaction.guild.get_channel(dados["canal_id"])
            if canal:
                await asyncio.sleep(3)
                await canal.delete()

# ================= EVENTS =================

@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")
    canal = bot.get_channel(CANALETA_SOLICITAR_SET_ID)
    async for msg in canal.history(limit=5):
        if msg.author == bot.user:
            await msg.delete()

    await canal.send(
        embed=Embed(
            title="Segurança Pública | Solicitar Funcional",
            description="Clique no botão abaixo para iniciar sua solicitação.",
            color=discord.Color.dark_gray()
        ),
        view=TicketView()
    )

@bot.event
async def on_member_join(member):
    role = member.guild.get_role(CARGO_NOVATO_ID)
    if role:
        await member.add_roles(role)

bot.run(TOKEN)
