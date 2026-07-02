"""Handlers do /ask: coach conversacional (corrida ou assunto geral)."""

import datetime as dt
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers_common import _authorized, _profile, _run_button_label
from bot.handlers_nutrition import _comi_process_text, _food_like, on_text_nutrition
from bot.runs import filter_runs
from src.extractors import activity_from_garmin
import bot.ask as ask
from bot.ask import build_run_context as ask_build_run, build_general_context as ask_build_general
from src.ai_coach import ask_coach


_ASK_KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("🏃 Corrida", callback_data="ask:run"),
    InlineKeyboardButton("💬 Outro assunto", callback_data="ask:geral"),
]])
_ASK_FIM_KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("✋ finalizar", callback_data="ask:fim")]])


def _profile_file_exists() -> bool:
    return Path("athlete_profile.json").exists()


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    if context.bot_data.get("anthropic") is None:
        await update.message.reply_text("🤖 Coach indisponível agora (sem ANTHROPIC_API_KEY).")
        return
    # ask_coach exige o perfil; sem ele o erro viraria um "não consegui responder" opaco
    if not _profile_file_exists():
        await update.message.reply_text(
            "🤖 Coach precisa do athlete_profile.json na raiz do projeto (não encontrei). "
            "Crie o arquivo conforme o CLAUDE.md e tenta de novo.")
        return
    await update.message.reply_text("Sobre o quê? 👇", reply_markup=_ASK_KB)


async def on_ask_button(update, context):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    data = q.data
    if data in ("ask:food:comi", "ask:food:coach"):
        text = context.user_data.pop("ask_food_pending", None)
        if not text:
            await q.edit_message_text("Sessão expirada — manda de novo.")
            return
        if data == "ask:food:comi":
            await q.edit_message_text("🍽 Registrando refeição:")
            await _comi_process_text(q.message.reply_text, context, text)
        else:
            await q.edit_message_text("💬 Perguntando ao coach…")
            await _ask_turn(q.message.reply_text, context, text)
        return
    if data == "ask:fim":
        ask.close_thread(context.user_data)
        await q.edit_message_reply_markup(reply_markup=None)  # tira o botão, mantém a resposta
        await q.message.reply_text("Conversa encerrada. ✋ (/ask pra recomeçar)")
        return
    if data == "ask:geral":
        ctx = ask_build_general(context.bot_data["db"], context.bot_data["db_path"],
                                _profile(context), dt.date.today().isoformat())
        ask.open_thread(context.user_data, mode="geral", run_id=None, context=ctx)
        await q.edit_message_text("Manda tua pergunta 👇")
        return
    if data == "ask:run":
        client = context.bot_data["client"]
        try:
            runs = filter_runs(client.get_activities(7, fresh=True))[:8]
        except Exception:  # noqa: BLE001
            await q.edit_message_text("Não consegui buscar tuas corridas agora.")
            return
        if not runs:
            await q.edit_message_text("Nenhuma corrida recente encontrada.")
            return
        db = context.bot_data["db"]
        for r in runs:
            db.upsert_activity(activity_from_garmin(r))
        teclado = [[InlineKeyboardButton(_run_button_label(r),
                    callback_data=f"ask:pick:{r['activityId']}")] for r in runs]
        await q.edit_message_text("Qual corrida?", reply_markup=InlineKeyboardMarkup(teclado))
        return
    if data.startswith("ask:pick:"):
        activity_id = int(data.split(":")[-1])
        ctx = ask_build_run(context.bot_data["db"], context.bot_data["client"], activity_id)
        ask.open_thread(context.user_data, mode="run", run_id=activity_id, context=ctx)
        await q.edit_message_text("Manda tua pergunta sobre essa corrida 👇")
        return


async def on_text_macros(update, context):
    """Roteia texto solto: thread /ask ativa > fluxos de nutrição (macros/comida)."""
    if not _authorized(update, context):
        return
    # thread /ask ativa tem prioridade sobre o fluxo de macros — mas texto que
    # parseia 100% como comida ("30g frango") provavelmente é refeição esquecida
    # com a thread aberta: pergunta antes de mandar pro coach.
    if ask.is_active(context.user_data):
        text = update.message.text.strip()
        if _food_like(text, context.bot_data["db_path"]):
            context.user_data["ask_food_pending"] = text
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("🍽 registrar refeição", callback_data="ask:food:comi"),
                InlineKeyboardButton("💬 perguntar ao coach", callback_data="ask:food:coach"),
            ]])
            await update.message.reply_text(
                "Isso parece comida. Registrar como refeição ou é pergunta pro coach?",
                reply_markup=kb)
            return
        await _handle_ask_turn(update, context)
        return
    await on_text_nutrition(update, context)


def _split_message(text: str, limit: int = 4000) -> list[str]:
    """Quebra `text` em pedaços de no máximo `limit` chars.

    Tenta cortar na última quebra de linha dentro da janela (preserva
    parágrafos/linhas); sem quebra disponível, corta duro em `limit`.
    ``"".join(_split_message(text, limit)) == text`` sempre.
    """
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    restante = text
    while len(restante) > limit:
        janela = restante[:limit]
        corte = janela.rfind("\n")
        if corte <= 0:
            corte = limit
        else:
            corte += 1  # inclui a quebra de linha no pedaço atual
        parts.append(restante[:corte])
        restante = restante[corte:]
    if restante:
        parts.append(restante)
    return parts


_ASK_STYLE = (
    "Você está numa conversa curta por Telegram. Responda de forma objetiva e direta ao ponto: "
    "vá direto à resposta, sem introdução nem repetir a pergunta. Poucas frases; use no máximo "
    "1-2 parágrafos curtos, só estendendo se a pergunta pedir. TEXTO PURO, SEM markdown: nada de "
    "asteriscos, hashtags, negrito ou listas formatadas. Se precisar listar, use travessão simples. "
    "Fale como um coach que manda mensagem no chat, não como um artigo."
)


async def _handle_ask_turn(update, context):
    await _ask_turn(update.message.reply_text, context, update.message.text.strip())


async def _ask_turn(reply, context, pergunta: str):
    ask.append_user(context.user_data, pergunta)
    try:
        resp = ask_coach(ask.history(context.user_data),
                         ask.get_context(context.user_data), depth="deep",
                         extra_system=_ASK_STYLE)
    except Exception:  # noqa: BLE001 — mantém a thread aberta pra nova tentativa
        logging.exception("ask_coach falhou no /ask")
        # remove a pergunta que não foi respondida do histórico
        ask.pop_last(context.user_data)
        await reply("Não consegui responder agora, tenta de novo.")
        return
    ask.append_assistant(context.user_data, resp)
    pedacos = _split_message(resp)
    for pedaco in pedacos[:-1]:
        await reply(pedaco)
    await reply(pedacos[-1], reply_markup=_ASK_FIM_KB)
