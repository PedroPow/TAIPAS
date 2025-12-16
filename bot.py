from unicodedata import name
import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from discord import Embed
import asyncio
import os
import sys

sys.modules['audioop'] = None

# ================= BOT =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= CONFIG =================
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

solicitacoes_abertas = {}

# ================= VALIDAÇÃO =================
def validar_cargos_companhia(guild: discord.Guild, companhia: str):
    erros = []

    cargo_companhia = CARGOS_COMPANHIA.get(companhia)
    if not cargo_companhia or not guild.get_role(cargo_companhia):
        erros.append(f"Cargo da companhia inválido: {companhia}")

    for nome, role_id in PATENTES_ESPECIALIZADAS.get(companhia, {}).items():
        if not guild.get_role(role_id):
            erros.append(f"Patente inválida: {nome}")

    return erros


def get_patentes_para(companhia):
    return PATENTES_ESPECIALIZADAS.get(companhia, {})

# ================= VIEW BOTÃO =================
class TicketView(View):
    @discord.ui.button(label="Solicitar Funcional", style=discord.ButtonStyle.secondary, custom_id="iniciar_pedido")
    async def abrir_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        user = interaction.user

        if user.id in solicitacoes_abertas:
            await interaction.response.send_message(
                "⚠️ Você já possui um ticket aberto.", ephemeral=True
            )
            return

        # 🔒 valida cargos antes de criar ticket
        erros = []
        for companhia in COMPANHIAS_CHANNEL.keys():
            erros.extend(validar_cargos_companhia(guild, companhia))

        if erros:
            await interaction.response.send_message(
                "❌ Sistema de SET indisponível:\n\n" +
                "\n".join(f"• {e}" for e in erros),
                ephemeral=True
            )
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

        solicitacoes_abertas[user.id] = {"canal_id": canal.id}

        view = View(timeout=None)
        view.add_item(SelectCompanhia(user.id))
        await canal.send(f"{user.mention}, selecione sua companhia:", view=view)

        await interaction.response.send_message(
            "🎟️ Ticket criado com sucesso.", ephemeral=True
        )

# ================= SELECTS =================
class SelectCompanhia(Select):
    def __init__(self, user_id):
        self.user_id = user_id
        options = [discord.SelectOption(label=n, value=n) for n in COMPANHIAS_CHANNEL]
        super().__init__(placeholder="Escolha sua companhia", options=options)

    async def callback(self, interaction: discord.Interaction):
        companhia = self.values[0]
        patentes = get_patentes_para(companhia)

        view = View(timeout=None)
        view.add_item(SelectPatente(self.user_id, companhia, patentes))
        await interaction.response.send_message(
            f"Companhia **{companhia}** selecionada. Escolha a patente:",
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
        patente_nome = self.values[0]
        patente_id = self.patentes[patente_nome]
        companhia_id = CARGOS_COMPANHIA[self.companhia]

        await interaction.response.send_modal(
            DadosPessoaisModal(
                self.user_id,
                self.companhia,
                patente_nome,
                patente_id,
                companhia_id
            )
        )

# ================= MODAL =================
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
        solicitacoes_abertas[self.user_id].update({
            "nome": self.nome.value,
            "passaporte": self.passaporte.value,
            "patente_id": self.patente_id,
            "companhia_id": self.companhia_id
        })

        embed = Embed(
            title="Solicitação de Funcional",
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

        await interaction.response.send_message(
            "✅ Solicitação enviada para avaliação.", ephemeral=True
        )

# ================= CONFIRMAÇÃO =================
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

        membro = interaction.guild.get_member(self.user_id)

        novo_apelido = f"#{dados['passaporte']} | {dados['nome']}"
        try:
            await membro.edit(nick=novo_apelido)
        except:
            pass

        novato = interaction.guild.get_role(CARGO_NOVATO_ID)
        if novato and novato in membro.roles:
            await membro.remove_roles(novato)

        cargo_patente = interaction.guild.get_role(dados['patente_id'])
        cargo_companhia = interaction.guild.get_role(dados['companhia_id'])

        if not cargo_patente or not cargo_companhia:
            await interaction.response.send_message(
                "❌ Erro ao aplicar cargos. Verifique os IDs.", ephemeral=True
            )
            return

        await membro.add_roles(cargo_patente, cargo_companhia)

        await interaction.response.send_message(
            f"✅ SET confirmado. Nick alterado para **{novo_apelido}**.", ephemeral=True
        )

        canal = bot.get_channel(dados['canal_id'])
        if canal:
            await asyncio.sleep(5)
            await canal.delete()

    @discord.ui.button(label="❌ Fechar Solicitação", style=discord.ButtonStyle.danger)
    async def fechar(self, interaction: discord.Interaction, button: Button):
        dados = solicitacoes_abertas.pop(self.user_id, None)
        await interaction.response.send_message("🗑️ Solicitação cancelada.", ephemeral=True)

        if dados:
            canal = bot.get_channel(dados['canal_id'])
            if canal:
                await asyncio.sleep(5)
                await canal.delete()

# ================= EVENTS =================
@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user}")

    canal = bot.get_channel(CANALETA_SOLICITAR_SET_ID)
    async for msg in canal.history(limit=10):
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
        await member.add_roles(role, reason="Novo membro")

# ================= START =================
bot.run(TOKEN)
