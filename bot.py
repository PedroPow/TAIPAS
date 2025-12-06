# bot_set_complete.py
# 🔥 BOT COMPLETO E OTIMIZADO (versão final)
# Requer: discord.py 2.3+, python 3.10+ recommended
# Como usar:
# 1) Instale: pip install -U "discord.py[voice]" (ou apenas discord.py)
# 2) Crie um arquivo .env com TOKEN=seu_token (ou defina variavel de ambiente)
# 3) Ajuste os IDs nas configurações abaixo
# 4) Rode: python bot_set_complete.py

import os
import json
import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Button, Select, Modal, TextInput

# ========== CONFIGURAÇÕES - ajuste estes valores ==========
# Use TOKEN via env var por segurança (ex: export TOKEN="seu_token")
TOKEN = os.getenv("TOKEN") or "MTM0OTU1OTU5NTA2NDA5ODg4OA.GuNm4c.apESDYag98R5QW933ucUrVgn-pK8wLOjtf2GgU"

# IDs (preencha com seus IDs)
GUILD_ID = 1445599273595961546  # ID do servidor (opcional, facilita sync se quiser)
CATEGORY_TICKETS = 1445599394291253351       # ID da categoria onde tickets serão criados
CANAL_SETS = 1446706930293801102            # ID do canal onde a staff recebe os sets
CANAL_BOTAO_FIXO = 1445599273595961549        # ID do canal para postar o botão fixo
LOG_CHANNEL_ID = 1445599309176504491         # ID do canal de logs
# Cargo inicial "SEM SET" (0 para ignorar)
CARGO_INICIAL = 1446708434509627523

# Roles autorizadas a aprovar/recusar (IDs)
ALLOWED_APPROVERS = ([1446690848027836449], [1446709225240662037])

# Mapas: preencha com os role IDs (use 0 para ignorar)
CARGO_MAP = {
    "Gerente": 1446707117380734996, 
    "Soldado": 1446707139643965644, 
    "Vapor": 1446707085114085417, 
}
QUEBRADA_MAP = {
    "Zona Leste": 1446707302131302472,
    "Zona Norte": 1446707265208975411,
    "Zona Sul": 1446707458448953365,
    "Zona Oeste": 1446707347329384489,
    "Centro": 1446707233508561067,
}

# Lista de opções para os selects (capturado das chaves dos maps)
QUEBRADAS = list(QUEBRADA_MAP.keys())
CARGOS = list(CARGO_MAP.keys())

# Arquivos de persistência local
DATA_FOLDER = "data"
BLACKLIST_FILE = os.path.join(DATA_FOLDER, "blacklist.json")
PENDING_FILE = os.path.join(DATA_FOLDER, "pending_sets.json")

# Caminho local para logo (opcional)
LOGO_PATH = "/mnt/data/IMAGEM_NORMAL_NATAL.png"
LOGO_FILENAME = "logo.png"

# Formato de nick
NICK_FORMAT = "{id} | {vulgo}"

# Timeout para respostas (em segundos)
RESPONSE_TIMEOUT = 300

# ===========================================================
# =========== Inicialização do bot e utilitários ============
# ===========================================================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# garante pasta data
os.makedirs(DATA_FOLDER, exist_ok=True)

def _load_json(path: str, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return default

def _save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

blacklist = _load_json(BLACKLIST_FILE, {"ids": []})
pending_sets = _load_json(PENDING_FILE, {"sets": []})

def is_approver(member: discord.Member) -> bool:
    if member is None:
        return False
    for r in member.roles:
        if r.id in ALLOWED_APPROVERS:
            return True
    return member.guild_permissions.manage_guild or member.guild_permissions.kick_members

def add_pending(entry: dict):
    pending_sets["sets"].append(entry)
    _save_json(PENDING_FILE, pending_sets)

def remove_pending_by_ticket(channel_id: int):
    original = len(pending_sets["sets"])
    pending_sets["sets"] = [s for s in pending_sets["sets"] if s.get("ticket_channel_id") != channel_id]
    if len(pending_sets["sets"]) != original:
        _save_json(PENDING_FILE, pending_sets)

def find_pending_by_staff_msg(message_id: int) -> Optional[dict]:
    for s in pending_sets["sets"]:
        if s.get("staff_message_id") == message_id:
            return s
    return None

def find_pending_by_user(user_id: int) -> Optional[dict]:
    for s in pending_sets["sets"]:
        if s.get("user_id") == user_id:
            return s
    return None

def make_embed(title: str, description: str = "", color: int = 0x00FF38) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text="Sistema de SET • PCC Zona Leste")
    return e

async def safe_send(channel: discord.abc.Messageable, embed: discord.Embed, file_logo: bool = True, view: Optional[View] = None):
    try:
        if file_logo and os.path.exists(LOGO_PATH):
            await channel.send(embed=embed, view=view, file=discord.File(LOGO_PATH, filename=LOGO_FILENAME))
        else:
            await channel.send(embed=embed, view=view)
    except Exception:
        await channel.send(embed=embed, view=view)

# ===========================================================
# ========== Views / Modal / Buttons (fluxo SET) ============
# ===========================================================

class ModalSetFinal(Modal, title="📑 Finalizar SET"):
    nome = TextInput(label="Nome Completo", placeholder="Seu nome completo", max_length=100)
    vulgo = TextInput(label="Vulgo", placeholder="Como te chamam?", max_length=64)
    idd = TextInput(label="ID", placeholder="ID que usa no servidor", max_length=50)
    numerada = TextInput(label="Numerada", placeholder="Numerada (opcional)", required=False, max_length=50)
    aval = TextInput(label="Aval", placeholder="Quem te avaliou (opcional)", required=False, max_length=64)

    def __init__(self, user: discord.Member, ticket_channel: discord.TextChannel, quebrada: str, cargo: str):
        super().__init__()
        self.user = user
        self.ticket_channel = ticket_channel
        self.quebrada = quebrada
        self.cargo = cargo

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        staff_ch = guild.get_channel(CANAL_SETS)
        if staff_ch is None:
            await interaction.response.send_message("Erro: canal de staff não configurado ou não encontrado.", ephemeral=True)
            return

        data = {
            "user_id": self.user.id,
            "user_name": str(self.user),
            "ticket_channel_id": self.ticket_channel.id,
            "nome": self.nome.value,
            "vulgo": self.vulgo.value,
            "idd": self.idd.value,
            "numerada": self.numerada.value,
            "aval": self.aval.value,
            "quebrada": self.quebrada,
            "cargo": self.cargo,
            "timestamp": datetime.utcnow().isoformat()
        }

        embed = make_embed("☯️ NOVO SET RECEBIDO", color=0x00FF38)
        embed.add_field(name="Nome", value=data["nome"], inline=False)
        embed.add_field(name="Vulgo", value=data["vulgo"], inline=False)
        embed.add_field(name="ID", value=data["idd"], inline=False)
        embed.add_field(name="Numerada", value=data["numerada"] or "—", inline=False)
        embed.add_field(name="Aval", value=data["aval"] or "—", inline=False)
        embed.add_field(name="Quebrada", value=data["quebrada"], inline=True)
        embed.add_field(name="Cargo", value=data["cargo"], inline=True)
        embed.add_field(name="Ticket", value=f"<#{self.ticket_channel.id}>", inline=False)
        embed.set_thumbnail(url=f"attachment://{LOGO_FILENAME}")

        view = ApproveDenyView(data)
        # Garantir envio do embed e salvar staff message id
        try:
            sent = await staff_ch.send(embed=embed, view=view, file=discord.File(LOGO_PATH, filename=LOGO_FILENAME)) if os.path.exists(LOGO_PATH) else await staff_ch.send(embed=embed, view=view)
        except Exception:
            sent = await staff_ch.send(embed=embed, view=view)

        data["staff_message_id"] = sent.id
        add_pending(data)

        await interaction.response.send_message("📨 Seu SET foi enviado para análise da staff.", ephemeral=True)


class SelectEtapa1(View):
    def __init__(self, user: discord.Member, ticket_channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.user = user
        self.ticket_channel = ticket_channel
        self.chosen_quebrada = None
        self.chosen_cargo = None

        # quebrada select
        self.q_select = Select(
            placeholder="Selecione sua Quebrada",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=q, value=q) for q in QUEBRADAS],
            custom_id=f"select_quebrada_{user.id}"
        )
        self.q_select.callback = self._quebrada_callback
        self.add_item(self.q_select)

        # cargo select
        self.c_select = Select(
            placeholder="Selecione seu Cargo",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=c, value=c) for c in CARGOS],
            custom_id=f"select_cargo_{user.id}"
        )
        self.c_select.callback = self._cargo_callback
        self.add_item(self.c_select)

    async def _quebrada_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Isso não é para você.", ephemeral=True)
        self.chosen_quebrada = interaction.data["values"][0]
        if self.chosen_cargo:
            modal = ModalSetFinal(self.user, self.ticket_channel, self.chosen_quebrada, self.chosen_cargo)
            return await interaction.response.send_modal(modal)
        await interaction.response.send_message(f"🏙️ Quebrada selecionada: **{self.chosen_quebrada}**", ephemeral=True)

    async def _cargo_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Isso não é para você.", ephemeral=True)
        self.chosen_cargo = interaction.data["values"][0]
        if self.chosen_quebrada:
            modal = ModalSetFinal(self.user, self.ticket_channel, self.chosen_quebrada, self.chosen_cargo)
            return await interaction.response.send_modal(modal)
        await interaction.response.send_message(f"🔰 Cargo selecionado: **{self.chosen_cargo}**", ephemeral=True)


class ApproveDenyView(View):
    """
    View com botões de Aprovar / Recusar.
    Criada por set enviado; ao criar armazenamos staff_message_id para persistir.
    """
    def __init__(self, data: dict):
        super().__init__(timeout=None)
        self.data = data

        # Observação: para persistência após restart, re-criaremos instâncias a partir do pending_sets.json
        # custom_id feito automaticamente pelo discord.py se não informado; persistência do callback é
        # garantida por `bot.add_view(view_instance)` no on_ready ao restaurar pendings.

    async def _authorized_or_reply(self, interaction: discord.Interaction) -> bool:
        if not is_approver(interaction.user):
            await interaction.response.send_message("🔒 Você não tem permissão para essa ação.", ephemeral=True)
            return False
        return True

@discord.ui.button(label="✔️ ACEITAR", style=discord.ButtonStyle.green)
async def aceitar(self, interaction: discord.Interaction, button: Button):
    if not await self._authorized_or_reply(interaction):
        return

    await interaction.response.defer(ephemeral=True)  # dá um tempo para processar

    guild = interaction.guild
    member = guild.get_member(self.data["user_id"])
    # se get_member retornar None (cache), buscar via API
    if member is None:
        try:
            member = await guild.fetch_member(self.data["user_id"])
        except Exception as e:
            print(f"[ERRO] não consegui obter o membro {self.data['user_id']}: {e}")
            return await interaction.followup.send("❌ Não foi possível encontrar o usuário no servidor.", ephemeral=True)

    ticket_ch = guild.get_channel(self.data["ticket_channel_id"])

    # remove cargo inicial se configurado
    if CARGO_INICIAL:
        try:
            role_ini = guild.get_role(CARGO_INICIAL)
            if role_ini and member:
                await member.remove_roles(role_ini, reason="SET aprovado")
        except Exception as e:
            print(f"[WARN] falha ao remover cargo inicial: {e}")

    # função auxiliar para adicionar role com checagens
    async def try_add_role(role_id: int, reason: str) -> bool:
        if not role_id:
            return False
        role = guild.get_role(role_id)
        if role is None:
            print(f"[WARN] role id {role_id} não existe no servidor.")
            return False
        # checar permissões/hierarquia do bot
        me = guild.me
        if not me.guild_permissions.manage_roles:
            print("[ERRO] bot não tem permission manage_roles")
            return False
        if role.position >= me.top_role.position:
            print(f"[ERRO] não posso gerenciar o role {role.name} porque está acima ou no mesmo nível que meu top role.")
            return False
        try:
            await member.add_roles(role, reason=reason)
            return True
        except Exception as e:
            print(f"[ERRO] falha ao adicionar role {role.name} a {member}: {e}")
            return False

        # --------------------------
        # 1) Cargo da Função
        # --------------------------
        try:
            role_id = CARGO_MAP.get(self.data["cargo"], 0)
            if role_id:
                role_funcao = guild.get_role(role_id)
                if role_funcao:
                    await member.add_roles(role_funcao, reason="SET aprovado - cargo da função")
        except Exception:
            pass

        # --------------------------
        # 2) Cargo da Quebrada
        # --------------------------
        try:
            qrole_id = QUEBRADA_MAP.get(self.data["quebrada"], 0)
            if qrole_id:
                role_quebrada = guild.get_role(qrole_id)
                if role_quebrada:
                    await member.add_roles(role_quebrada, reason="SET aprovado - quebrada")
        except Exception:
            pass

        # --------------------------
        # 3) Cargo Fixo de Aprovado
        # --------------------------
        try:
            cargo_aprovado = guild.get_role(1446721622466629713)
            if cargo_aprovado:
                await member.add_roles(cargo_aprovado, reason="SET aprovado - cargo fixo de aprovados")
        except Exception:
            pass


    # renomeia (se possível)
    if member:
        try:
            await member.edit(nick=NICK_FORMAT.format(id=self.data["idd"], vulgo=self.data["vulgo"]), reason="SET aprovado")
        except Exception:
            pass

    # DM sucesso (tenta com logo)
    try:
        embed_dm = make_embed("✅ SET APROVADO", f"Parabéns {member.mention if member else self.data['user_name']}! Seu SET foi aprovado. Seja bem-vindo à família.")
        if os.path.exists(LOGO_PATH):
            file = discord.File(LOGO_PATH, filename=LOGO_FILENAME)
            if member:
                try:
                    await member.send(embed=embed_dm, file=file)
                except Exception:
                    pass
        else:
            if member:
                try:
                    await member.send(embed=embed_dm)
                except Exception:
                    pass
    except Exception:
        pass

    # log para canal de logs (detalhado)
    try:
        log_ch = guild.get_channel(LOG_CHANNEL_ID)
        if log_ch:
            log_embed = make_embed("🟢 SET APROVADO", f"Aprovado por: {interaction.user.mention}\nMembro: <@{self.data['user_id']}>")
            log_embed.add_field(name="Nome", value=self.data.get("nome","—"), inline=True)
            log_embed.add_field(name="Vulgo", value=self.data.get("vulgo","—"), inline=True)
            log_embed.add_field(name="ID", value=self.data.get("idd","—"), inline=True)
            log_embed.add_field(name="Cargo", value=self.data.get("cargo","—"), inline=True)
            log_embed.add_field(name="Quebrada", value=self.data.get("quebrada","—"), inline=True)
            log_embed.add_field(name="Ticket", value=f"<#{self.data['ticket_channel_id']}>", inline=False)
            if os.path.exists(LOGO_PATH):
                try:
                    await log_ch.send(embed=log_embed, file=discord.File(LOGO_PATH, filename=LOGO_FILENAME))
                except:
                    await log_ch.send(embed=log_embed)
            else:
                await log_ch.send(embed=log_embed)
    except Exception:
        pass

    # fecha ticket
    try:
        if ticket_ch:
            await ticket_ch.delete(reason="SET aprovado - encerrando ticket")
    except Exception:
        pass

    # remove pending e desabilita os botões
    remove_pending_by_ticket(self.data["ticket_channel_id"])
    self.clear_items()
    try:
        await interaction.message.edit(view=self)
    except Exception:
        pass

    await interaction.followup.send("✔️ SET aprovado com sucesso.", ephemeral=True)



    @discord.ui.button(label="❌ RECUSAR", style=discord.ButtonStyle.red)
    async def recusar(self, interaction: discord.Interaction, button: Button):
        if not await self._authorized_or_reply(interaction): return

        guild = interaction.guild
        member = guild.get_member(self.data["user_id"])
        ticket_ch = guild.get_channel(self.data["ticket_channel_id"])

        # DM reprovação
        try:
            embed_dm = make_embed("❌ SET REPROVADO", f"{member.mention if member else self.data['user_name']}, seu SET foi reprovado. Revise e tente novamente.")
            if os.path.exists(LOGO_PATH):
                if member:
                    try: await member.send(embed=embed_dm, file=discord.File(LOGO_PATH, filename=LOGO_FILENAME))
                    except: pass
            else:
                if member:
                    try: await member.send(embed=embed_dm)
                    except: pass
        except Exception:
            pass

        # log reprovação
        try:
            log_ch = guild.get_channel(LOG_CHANNEL_ID)
            if log_ch:
                log_embed = make_embed("🔴 SET REPROVADO", f"Reprovado por: {interaction.user.mention}\nMembro: <@{self.data['user_id']}>")
                log_embed.add_field(name="Nome", value=self.data.get("nome","—"), inline=True)
                log_embed.add_field(name="Vulgo", value=self.data.get("vulgo","—"), inline=True)
                log_embed.add_field(name="ID", value=self.data.get("idd","—"), inline=True)
                log_embed.add_field(name="Cargo", value=self.data.get("cargo","—"), inline=True)
                log_embed.add_field(name="Quebrada", value=self.data.get("quebrada","—"), inline=True)
                log_embed.add_field(name="Ticket", value=f"<#{self.data['ticket_channel_id']}>", inline=False)
                if os.path.exists(LOGO_PATH):
                    try:
                        await log_ch.send(embed=log_embed, file=discord.File(LOGO_PATH, filename=LOGO_FILENAME))
                    except:
                        await log_ch.send(embed=log_embed)
                else:
                    await log_ch.send(embed=log_embed)
        except Exception:
            pass

        # fechar ticket
        try:
            if ticket_ch:
                await ticket_ch.delete(reason="SET reprovado - encerrando ticket")
        except Exception:
            pass

        remove_pending_by_ticket(self.data["ticket_channel_id"])
        self.clear_items()
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

        await interaction.response.send_message("❌ SET reprovado e usuário notificado.", ephemeral=True)


class FixedButtonView(View):
    """Botão fixo postado em CANAL_BOTAO_FIXO para abrir tickets."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📋 Abrir SET", style=discord.ButtonStyle.gray, custom_id="fixed_open_set")
    async def open_set(self, interaction: discord.Interaction, button: Button):
        member = interaction.user
        guild = interaction.guild

        # blacklist check
        if member.id in blacklist.get("ids", []):
            try: await member.send("Você está impedido de abrir SET (blacklist).")
            except: pass
            return await interaction.response.send_message("🚫 Você não pode abrir um SET.", ephemeral=True)

        # evita duplicação de ticket
        existing = discord.utils.get(guild.text_channels, name=f"set-{member.id}")
        if existing:
            return await interaction.response.send_message(f"Você já tem um ticket: {existing.mention}", ephemeral=True)

        # cria canal na categoria configurada
        category = discord.utils.get(guild.categories, id=CATEGORY_TICKETS) if CATEGORY_TICKETS else None
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        try:
            ticket = await guild.create_text_channel(name=f"set-{member.id}", category=category, overwrites=overwrites, reason="Ticket de SET criado")
        except Exception as e:
            await interaction.response.send_message("❌ Erro ao criar ticket. Verifique permissões do bot.", ephemeral=True)
            return

        # atribui cargo inicial opcional
        if CARGO_INICIAL:
            try:
                role_ini = guild.get_role(CARGO_INICIAL)
                if role_ini:
                    await member.add_roles(role_ini, reason="Recebeu cargo 'sem set' ao abrir ticket")
            except Exception:
                pass

        # envia embed inicial com selects
        embed = make_embed("☯️ Iniciar SET", "Selecione sua Quebrada e Cargo abaixo para continuar.")
        embed.set_thumbnail(url=f"attachment://{LOGO_FILENAME}")
        view = SelectEtapa1(member, ticket)
        try:
            if os.path.exists(LOGO_PATH):
                await ticket.send(embed=embed, view=view, file=discord.File(LOGO_PATH, filename=LOGO_FILENAME))
            else:
                await ticket.send(embed=embed, view=view)
        except Exception:
            await ticket.send(embed=embed, view=view)

        await interaction.response.send_message(f"✅ Ticket criado: {ticket.mention}", ephemeral=True)

# ===========================================================
# ================== Painel administrativo ==================
# ===========================================================
class PanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📋 Ver Pendentes", style=discord.ButtonStyle.blurple, custom_id="panel_pendentes")
    async def ver_pendentes(self, interaction: discord.Interaction, button: Button):
        # lista pendings simplificada
        lines = []
        for s in pending_sets.get("sets", []):
            lines.append(f"- `{s.get('nome','?')}` / `{s.get('vulgo','?')}` — ticket: <#{s.get('ticket_channel_id')}> — staff msg id: `{s.get('staff_message_id')}`")
        if not lines:
            return await interaction.response.send_message("📭 Não há SETs pendentes.", ephemeral=True)
        await interaction.response.send_message("📌 SETs pendentes:\n" + "\n".join(lines), ephemeral=True)

    @discord.ui.button(label="⚠ Limpar Tickets Bugados", style=discord.ButtonStyle.red, custom_id="panel_limpar_bug")
    async def limpar_bugados(self, interaction: discord.Interaction, button: Button):
        # tenta apagar canais sem usuários
        guild = interaction.guild
        removed = 0
        for s in list(pending_sets.get("sets", [])):
            tid = s.get("ticket_channel_id")
            ch = guild.get_channel(tid)
            if ch is None:
                remove_pending_by_ticket(tid)
                removed += 1
        await interaction.response.send_message(f"🧹 Removidos {removed} entradas pendentes inválidas.", ephemeral=True)

    @discord.ui.button(label="🚫 Blacklist", style=discord.ButtonStyle.gray, custom_id="panel_blacklist")
    async def open_blacklist(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("📂 Use os comandos `!blacklist add/remove/list` no chat para gerenciar.", ephemeral=True)

# comandos de console/admin
@bot.command()
@commands.has_permissions(administrator=True)
async def resend_panel(ctx):
    """Reenvia o painel fixo no canal configurado (admin)."""
    ch = ctx.guild.get_channel(CANAL_BOTAO_FIXO) if CANAL_BOTAO_FIXO else None
    if not ch:
        return await ctx.send("Canal do botão fixo não configurado ou não encontrado.")
    embed = make_embed("☯️ SISTEMA DE SET — PCC Zona Leste", "Clique no botão abaixo para iniciar seu SET.")
    embed.set_thumbnail(url=f"attachment://{LOGO_FILENAME}")
    try:
        if os.path.exists(LOGO_PATH):
            await ch.send(embed=embed, view=FixedButtonView(), file=discord.File(LOGO_PATH, filename=LOGO_FILENAME))
        else:
            await ch.send(embed=embed, view=FixedButtonView())
        await ctx.send("✅ Painel fixo enviado.")
    except Exception as e:
        await ctx.send(f"Erro ao enviar painel: {e}")

# Blacklist commands (prefix-style)
@bot.group(name="blacklist", invoke_without_command=True)
@commands.has_permissions(manage_guild=True)
async def bl_group(ctx):
    await ctx.send("Use: `!blacklist add @user motivo` | `!blacklist remove @user` | `!blacklist list`")

@bl_group.command(name="add")
@commands.has_permissions(manage_guild=True)
async def bl_add(ctx, member: discord.Member, *, motivo: str = "Sem motivo informado"):
    if member.id in blacklist.get("ids", []):
        return await ctx.send("Usuário já está na blacklist.")
    blacklist["ids"].append(member.id)
    _save_json(BLACKLIST_FILE, blacklist)
    await ctx.send(f"✅ {member.mention} adicionado à blacklist. Motivo: {motivo}")

@bl_group.command(name="remove")
@commands.has_permissions(manage_guild=True)
async def bl_remove(ctx, member: discord.Member):
    if member.id not in blacklist.get("ids", []):
        return await ctx.send("Usuário não está na blacklist.")
    blacklist["ids"].remove(member.id)
    _save_json(BLACKLIST_FILE, blacklist)
    await ctx.send(f"✅ {member.mention} removido da blacklist.")

@bl_group.command(name="list")
@commands.has_permissions(manage_guild=True)
async def bl_list(ctx):
    if not blacklist.get("ids", []):
        return await ctx.send("Blacklist vazia.")
    lines = [f"<@{uid}> (`{uid}`)" for uid in blacklist["ids"]]
    await ctx.send("Lista da blacklist:\n" + "\n".join(lines))

# ===========================================================
# ===================== Startup / Restore ===================
# ===========================================================
@bot.event
async def on_ready():
    print(f"Bot online como {bot.user} (ID: {bot.user.id})")
    # registrar views persistentes (botões que não expiram)
    bot.add_view(FixedButtonView())
    bot.add_view(PanelView())

    # restaurar views para pendings (para permitir callbacks em mensagens de staff depois de restart)
    restored = 0
    guild = None
    try:
        guild = bot.get_guild(GUILD_ID) if GUILD_ID else None
    except Exception:
        guild = None

    for s in list(pending_sets.get("sets", [])):
        staff_msg_id = s.get("staff_message_id")
        if staff_msg_id is None:
            continue
        try:
            if guild:
                staff_channel = guild.get_channel(CANAL_SETS) if CANAL_SETS else None
                if staff_channel:
                    # Recria view com os dados e registra (callbacks serão chamados)
                    view = ApproveDenyView(s)
                    bot.add_view(view)  # registra a view para persistência
                    restored += 1
        except Exception:
            pass

    print(f"Restauradas {restored} pendências em memória.")

    # postar botão fixo se ainda não houver (tenta evitar duplicação)
    try:
        if CANAL_BOTAO_FIXO:
            ch = bot.get_channel(CANAL_BOTAO_FIXO)
            if ch:
                # procurar mensagens do bot recentes com o mesmo título (30 mensagens)
                recent = [m async for m in ch.history(limit=30)]
                already = False
                for m in recent:
                    if m.author == bot.user and m.embeds:
                        for e in m.embeds:
                            if e.title and "SISTEMA DE SET" in e.title:
                                already = True
                                break
                    if already:
                        break
                if not already:
                    embed = make_embed("☯️ SISTEMA DE SET — PCC Zona Leste", "Clique no botão abaixo para iniciar seu SET.")
                    embed.set_thumbnail(url=f"attachment://{LOGO_FILENAME}")
                    if os.path.exists(LOGO_PATH):
                        await ch.send(embed=embed, view=FixedButtonView(), file=discord.File(LOGO_PATH, filename=LOGO_FILENAME))
                    else:
                        await ch.send(embed=embed, view=FixedButtonView())
    except Exception as e:
        print("Erro ao postar botão fixo:", e)

# ===========================================================
# ==================== Run Bot ==============================
# ===========================================================
if __name__ == "__main__":
    if TOKEN == "TOKEN":
        print("ERRO: coloque seu TOKEN como variável de ambiente TOKEN ou no arquivo .env")
    else:
        bot.run(TOKEN)



