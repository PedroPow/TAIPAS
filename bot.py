from unicodedata import name
import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
from discord import Embed, TextStyle
import asyncio
import os
import sys
sys.modules['audioop'] = None


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# CONFIGURAÇÃO
TOKEN = os.getenv("TOKEN")
CANALETA_SOLICITAR_SET_ID = 1343398652349255758
CARGO_NOVATO_ID = 1345435302285545652
CATEGORIA_TICKET_ID = 1343398652349255757  # <- Substitua pelo ID correto da categoria dos tickets

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
    },


    
}
solicitacoes_abertas = {}

def get_patentes_para(companhia):

    # 1 — Se estiver nas especializadas
    if companhia in PATENTES_ESPECIALIZADAS:
        return PATENTES_ESPECIALIZADAS[companhia]

class TicketView(View):
    @discord.ui.button(label="Solicitar Funcional", style=discord.ButtonStyle.secondary, custom_id="iniciar_pedido")
    async def abrir_ticket(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        user = interaction.user

        if interaction.user.id in solicitacoes_abertas:
            await interaction.response.send_message("⚠️ Você já possui um ticket aberto.", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, id=CATEGORIA_TICKET_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        canal = await guild.create_text_channel(name=f"ticket-{user.name}", category=category, overwrites=overwrites)
        solicitacoes_abertas[user.id] = {"canal_id": canal.id}

        view = View(timeout=None)
        view.add_item(SelectCompanhia(user.id))
        await canal.send(f"{user.mention}, selecione sua companhia:", view=view)
        await interaction.response.send_message("🎟️ Ticket criado! Verifique o canal criado.", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.delete_original_response()
        except:
            pass

class SelectCompanhia(Select):
    def __init__(self, user_id):
        self.user_id = user_id
        options = [discord.SelectOption(label=nome, value=nome) for nome in COMPANHIAS_CHANNEL]
        super().__init__(placeholder="Escolha sua companhia", options=options, custom_id="select_companhia")

    async def callback(self, interaction: discord.Interaction):
        companhia = self.values[0]
        patentes = get_patentes_para(companhia)

        view = View(timeout=None)
        view.add_item(SelectPatente(self.user_id, companhia, patentes))
        await interaction.response.send_message(f"Companhia **{companhia}** selecionada. Agora selecione sua patente:", view=view, ephemeral=True)

class SelectPatente(Select):
    def __init__(self, user_id, companhia, patentes):
        self.user_id = user_id
        self.companhia = companhia
        self.patentes = patentes
        options = [discord.SelectOption(label=nome, value=nome) for nome in patentes]
        super().__init__(placeholder="Escolha sua patente", options=options, custom_id="select_patente")

    async def callback(self, interaction: discord.Interaction):
        patente_nome = self.values[0]
        patente_id = self.patentes[patente_nome]
        companhia_id = CARGOS_COMPANHIA[self.companhia]
        await interaction.response.send_modal(DadosPessoaisModal(self.user_id, self.companhia, patente_nome, patente_id, companhia_id))

class DadosPessoaisModal(Modal, title="Informe seus dados"):
    nome = TextInput(label="Nome Completo", required=True, max_length=80)
    passaporte = TextInput(label="Passaporte", required=True, max_length=20)

    def __init__(self, user_id, companhia, patente_nome, patente_id, companhia_id):
        super().__init__()
        self.user_id = user_id
        self.companhia = companhia
        self.patente_nome = patente_nome
        self.patente_id = patente_id
        self.companhia_id = companhia_id

    async def on_submit(self, interaction: discord.Interaction):
        nome = self.nome.value.strip()
        passaporte = self.passaporte.value.strip()
        solicitacoes_abertas[self.user_id].update({
            "patente_id": self.patente_id,
            "companhia_id": self.companhia_id,
            "nome": nome,
            "passaporte": passaporte
        })

        embed = Embed(title="Solicitar Funcional",
                      description=f"**Nome:** {nome}\n**Passaporte:** {passaporte}\n**Companhia:** {self.companhia}\n**Patente:** {self.patente_nome}",
                      color=discord.Color.dark_gray())
        embed.set_footer(text=f"Solicitante: {interaction.user}", icon_url=interaction.user.display_avatar.url)

        canal_logs = bot.get_channel(COMPANHIAS_CHANNEL[self.companhia])
        await canal_logs.send(embed=embed, view=ConfirmarOuFecharView(self.user_id))
        await interaction.response.send_message("✅ Solicitação enviada para avaliação.", ephemeral=True)

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
        if novato in membro.roles:
            await membro.remove_roles(novato)

        await membro.add_roles(
            interaction.guild.get_role(dados['patente_id']),
            interaction.guild.get_role(dados['companhia_id'])
        )


        await interaction.response.send_message(f"✅ SET confirmado. Nick alterado para **{novo_apelido}**.", ephemeral=True)
        
        # Fecha o canal do ticket
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

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    canal = bot.get_channel(CANALETA_SOLICITAR_SET_ID)
    async for msg in canal.history(limit=10):
        if msg.author == bot.user:
            await msg.delete()
    await canal.send(embed=Embed(
        title="Segurança Pública | Solicitar Funcional",
        description="Clique no botão abaixo para iniciar sua solicitação de funcional.",
        color=discord.Color.dark_gray()
    ), view=TicketView())

@bot.event
async def on_member_join(member):
    novato_role = member.guild.get_role(CARGO_NOVATO_ID)
    if novato_role:
        try:
            await member.add_roles(novato_role, reason="Novo membro entrou no servidor.")
            print(f"Cargo de novato atribuído a {member.name}")
        except discord.Forbidden:
            print(f"Permissão negada ao tentar dar cargo de novato a {member.name}")
        except discord.HTTPException as e:
            print(f"Erro ao atribuir cargo de novato: {e}")

TOKEN="MTM2MjIwODU1NjUwNTM2NjczMA.Gb6GC1.aO9KZi-vv92s8eVXPMdmGUXb5LtW2AtYSLFWeM"

bot.run(TOKEN)
