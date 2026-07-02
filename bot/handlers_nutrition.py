"""Handlers de nutrição: /comi, /dieta, /macros, /ref, /peso, /progresso, plano do dia."""

import datetime as dt
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.charts import nutrition_panel_png
from bot.handlers_common import _authorized, _profile
from bot.nutrition import (
    load_food_db, today_panel, resolve_unknowns,
    parse_peso_arg, build_progress_report,
)
from bot.nutrition_format import format_meal_confirm, format_macros_today
from src.nutrition.config import nutrition_config
from src.nutrition.meal_parser import parse_meal
from src.nutrition.label_vision import extract_label
import src.nutrition.store as store


_DP_MAP = {"dp:treino": (1, 0), "dp:corrida": (0, 1),
           "dp:ambos": (1, 1), "dp:descanso": (0, 0)}


def parse_day_plan_callback(data: str) -> tuple[int, int]:
    return _DP_MAP.get(data, (0, 0))


async def on_day_plan_button(update, context):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    treina, corre = parse_day_plan_callback(q.data)
    day = dt.date.today().isoformat()
    store.set_day_plan(context.bot_data["db_path"], day, treina, corre)
    await q.edit_message_text("Anotado o plano de hoje. Use /dieta pra ver os alvos.")


def parse_manual_macros(text: str):
    """Parse '120 24 3 1.5' -> {'kcal':120,'p':24,'c':3,'g':1.5}. Returns None on error."""
    parts = (text or "").replace(",", ".").split()
    if len(parts) != 4:
        return None
    try:
        kcal, p, c, g = (float(x) for x in parts)
    except ValueError:
        return None
    return {"kcal": kcal, "p": p, "c": c, "g": g}


async def cmd_comi(update, context):
    if not _authorized(update, context):
        return
    text = update.message.text.partition(" ")[2].strip()
    if not text:
        # fluxo guiado: pergunta a refeição; depois o usuário manda os alimentos aos poucos.
        context.user_data["comi"] = {"meal": None, "items": []}
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌅 café da manhã", callback_data="nut:meal:café da manhã"),
             InlineKeyboardButton("🍽 almoço", callback_data="nut:meal:almoço")],
            [InlineKeyboardButton("🥪 lanche", callback_data="nut:meal:lanche"),
             InlineKeyboardButton("🌙 janta", callback_data="nut:meal:janta")],
        ])
        await update.message.reply_text("Qual refeição?", reply_markup=kb)
        return
    await _comi_process_text(update.message.reply_text, context, text)


async def _comi_process_text(reply, context, text: str):
    """Parseia texto de refeição e oferece confirmação (fluxo /comi com texto)."""
    db_path = context.bot_data["db_path"]
    fdb = load_food_db(db_path)
    parsed = parse_meal(text, fdb, fuzzy=False)   # exato-only; IA preenche o resto

    # Desconhecidos → IA resolve e cacheia (source=ia); depois re-parseia com a base atualizada.
    desconhecidos = [it.get("name") for it in parsed.get("items", [])
                     if not it.get("recognized") and it.get("name")]
    client = context.bot_data.get("anthropic")
    if desconhecidos and client is not None:
        cfg = context.bot_data["cfg"]
        try:
            resolve_unknowns(db_path, desconhecidos, client, cfg.vision_model)
            fdb = load_food_db(db_path)
            parsed = parse_meal(text, fdb, fuzzy=False)
        except Exception:  # noqa: BLE001 — IA falhou: segue com o que reconheceu + botões
            pass

    context.user_data["pending_meal"] = parsed

    # Check for unrecognized items — offer cadastro buttons for the first one
    unrecognized = [it for it in parsed.get("items", []) if not it.get("recognized")]
    buttons = [
        InlineKeyboardButton("✅ salvar", callback_data="nut:save"),
        InlineKeyboardButton("✏️ corrigir", callback_data="nut:edit"),
    ]
    if unrecognized:
        context.user_data["pending_food"] = unrecognized[0].get("name") or unrecognized[0].get("raw", "")
        buttons += [
            InlineKeyboardButton("📷 foto da tabela", callback_data="nut:photo"),
            InlineKeyboardButton("⌨ digitar macros", callback_data="nut:manual"),
        ]

    kb = InlineKeyboardMarkup([buttons[:2], buttons[2:]] if len(buttons) > 2 else [buttons])
    await reply(format_meal_confirm(parsed), reply_markup=kb)


_COMI_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ finalizar", callback_data="nut:comi_fim"),
     InlineKeyboardButton("↩ desfazer último", callback_data="nut:comi_undo")],
    [InlineKeyboardButton("📷 foto da tabela", callback_data="nut:comi_foto")],
])


def _comi_running(comi: dict, extra=None) -> str:
    """Texto do acumulado da sessão /comi (itens já somados + eventuais não-reconhecidos)."""
    items = list(comi.get("items", [])) + list(extra or [])
    return format_meal_confirm({"meal": comi.get("meal"), "items": items})


async def _comi_add_foods(update, context, text: str):
    """Adiciona alimentos à sessão /comi: parse exato -> IA resolve -> acumula."""
    db_path = context.bot_data["db_path"]
    comi = context.user_data["comi"]
    fdb = load_food_db(db_path)
    parsed = parse_meal(text, fdb, fuzzy=False)
    desconhecidos = [it.get("name") for it in parsed["items"]
                     if not it.get("recognized") and it.get("name")]
    client = context.bot_data.get("anthropic")
    if desconhecidos and client is not None:
        try:
            resolve_unknowns(db_path, desconhecidos, client, context.bot_data["cfg"].vision_model)
            fdb = load_food_db(db_path)
            parsed = parse_meal(text, fdb, fuzzy=False)
        except Exception:  # noqa: BLE001 — IA falhou: segue com o reconhecido + foto
            pass
    recon = [it for it in parsed["items"] if it.get("recognized")]
    unrec = [it for it in parsed["items"] if not it.get("recognized")]
    comi["items"].extend(recon)
    msg = _comi_running(comi, extra=unrec)
    msg += "\n\nManda mais alimentos, ou finaliza."
    await update.message.reply_text(msg, reply_markup=_COMI_KB)


async def on_nutrition_button(update, context):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    db_path = context.bot_data["db_path"]
    day = dt.date.today().isoformat()
    if q.data.startswith("nut:meal:"):
        meal = q.data.split(":", 2)[2]
        context.user_data.setdefault("comi", {"meal": None, "items": []})["meal"] = meal
        await q.edit_message_text(
            f"🍽 {meal.capitalize()} — manda os alimentos (ex.: 100g arroz, 2 ovos). "
            "Vou somando.", reply_markup=_COMI_KB)
        return
    if q.data == "nut:comi_fim":
        comi = context.user_data.get("comi")
        if not comi or not comi.get("items"):
            context.user_data.pop("comi", None)
            await q.edit_message_text("Nada pra salvar.")
            return
        store.save_meal_items(db_path, day, comi.get("meal"), comi["items"])
        context.user_data.pop("comi", None)
        t = store.day_totals(db_path, day)
        await q.edit_message_text(
            f"✅ {(comi.get('meal') or 'refeição').capitalize()} salva. "
            f"Hoje: {round(t['kcal'])} kcal · P {t['p']:.0f}")
        return
    if q.data.startswith("nut:rmitem:"):
        try:
            item_id = int(q.data.split(":", 2)[2])
        except (ValueError, IndexError):
            await q.edit_message_text("Item inválido.")
            return
        store.delete_meal_item(db_path, item_id)
        txt, kb = _ref_view(db_path, day)
        await q.edit_message_text(txt, reply_markup=kb)
        return
    if q.data == "nut:comi_undo":
        comi = context.user_data.get("comi")
        if not comi or not comi.get("items"):
            await q.edit_message_text("Nada pra desfazer.", reply_markup=_COMI_KB)
            return
        removido = comi["items"].pop()
        msg = f"↩ tirei: {removido.get('food', '?')}\n\n" + _comi_running(comi)
        msg += "\n\nManda mais alimentos, ou finaliza."
        await q.edit_message_text(msg, reply_markup=_COMI_KB)
        return
    if q.data == "nut:comi_foto":
        context.user_data["comi_foto"] = True
        await q.edit_message_text(
            "Manda a foto da tabela nutricional do produto. Depois te peço a quantidade.")
        return
    if q.data == "nut:save":
        parsed = context.user_data.get("pending_meal")
        if not parsed:
            await q.edit_message_text("Nada pra salvar.")
            return
        store.save_meal_items(db_path, day, parsed.get("meal"), parsed["items"])
        context.user_data.pop("pending_meal", None)
        context.user_data.pop("pending_food", None)
        context.user_data.pop("awaiting_manual", None)
        t = store.day_totals(db_path, day)
        await q.edit_message_text(f"Salvo. Hoje: {round(t['kcal'])} kcal · P {t['p']:.0f}")
    elif q.data == "nut:edit":
        context.user_data.pop("pending_food", None)
        context.user_data.pop("awaiting_manual", None)
        await q.edit_message_text("Reenvie a refeição com /comi corrigindo o item.")
    elif q.data == "nut:del":
        ok = store.delete_last_meal_item(db_path, day)
        await q.edit_message_text("Última refeição apagada." if ok else "Nada pra apagar.")
    elif q.data == "nut:photo":
        name = context.user_data.get("pending_food") or ""
        await q.edit_message_text(
            f"Manda a foto da tabela nutricional de '{name}'.")
    elif q.data == "nut:foodsave":
        data = context.user_data.pop("pending_custom", None)
        context.user_data.pop("pending_food", None)
        context.user_data.pop("awaiting_manual", None)
        if data:
            store.add_custom_food(db_path, data["name"], data["base_unit"],
                                  data.get("porcao_g"), data["kcal"], data["p"],
                                  data["c"], data["g"])
            await q.edit_message_text(f"Cadastrado: {data['name']}. Refaça o /comi.")
        else:
            await q.edit_message_text("Sessão expirada. Refaça o /comi.")
    elif q.data == "nut:manual":
        name = (context.user_data.get("pending_custom") or {}).get("name") \
            or context.user_data.get("pending_food")
        context.user_data["awaiting_manual"] = name
        await q.edit_message_text(
            "Manda: kcal proteína carbo gordura (ex.: 120 24 3 1.5)")


def _ref_view(db_path, day):
    """(texto, teclado) das refeições de hoje — um 🗑 por item pra apagar."""
    items = store.list_meal_items(db_path, day)
    if not items:
        return "Nenhuma refeição registrada hoje.", None
    linhas = ["Refeições de hoje — toque pra apagar o item errado:"]
    botoes = []
    for it in items:
        food = it.get("food") or "?"
        linhas.append(f"• {(it.get('meal') or '').capitalize()}: {food} "
                      f"{round(it.get('grams') or 0)}g · {round(it.get('kcal') or 0)} kcal")
        botoes.append([InlineKeyboardButton(
            f"🗑 {food} {round(it.get('grams') or 0)}g",
            callback_data=f"nut:rmitem:{it['id']}")])
    return "\n".join(linhas), InlineKeyboardMarkup(botoes)


async def cmd_ref(update, context):
    if not _authorized(update, context):
        return
    db_path = context.bot_data["db_path"]
    txt, kb = _ref_view(db_path, dt.date.today().isoformat())
    await update.message.reply_text(txt, reply_markup=kb)


async def cmd_dieta(update, context):
    if not _authorized(update, context):
        return
    db_path = context.bot_data["db_path"]
    day = dt.date.today().isoformat()
    panel = today_panel(db_path, _profile(context), day)
    training_today = panel["today"]["training"]
    titulo = "Hoje (dia treino)" if training_today else "Hoje (descanso)"
    png = nutrition_panel_png(panel, titulo=titulo)
    await update.message.reply_photo(png)


async def on_photo(update, context):
    """Handle photo message: if pending_food set, extract label and confirm before saving."""
    if not _authorized(update, context):
        return
    name = context.user_data.get("pending_food")
    sessao_foto = context.user_data.get("comi_foto")
    if not name and not sessao_foto:
        return                                  # foto sem contexto de cadastro: ignora
    client = context.bot_data.get("anthropic")  # populated in Task 14
    model = context.bot_data["cfg"].vision_model
    photo = update.message.photo[-1]
    f = await photo.get_file()
    buf = await f.download_as_bytearray()
    data = extract_label(bytes(buf), client=client, model=model)
    if not data:
        await update.message.reply_text(
            "Não consegui ler a tabela. Manda os macros: kcal proteína carbo gordura "
            "(ex.: 120 24 3 1.5)")
        context.user_data["awaiting_manual"] = name or (data or {}).get("name")
        return
    # sessão /comi: leu os macros do rótulo; agora pede o NOME pro usuário.
    if sessao_foto and not name:
        context.user_data.pop("comi_foto", None)
        context.user_data["awaiting_food_name"] = data      # macros pendentes
        await update.message.reply_text(
            f"Li do rótulo: {round(data['kcal'])} kcal · P {data['p']:.0f} · "
            f"C {data['c']:.0f} · G {data['g']:.0f} (por {'porção' if data['base_unit']=='porcao' else '100g'}).\n"
            "Qual o nome desse alimento?")
        return
    data["name"] = name
    context.user_data["pending_custom"] = data
    base = "porção" if data["base_unit"] == "porcao" else "100g"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ salvar", callback_data="nut:foodsave"),
        InlineKeyboardButton("⌨ digitar", callback_data="nut:manual"),
    ]])
    await update.message.reply_text(
        f"Li ({base}): {round(data['kcal'])} kcal · P {data['p']:.0f} · "
        f"C {data['c']:.0f} · G {data['g']:.0f}. Confere?", reply_markup=kb)


def _food_like(text: str, db_path: str) -> bool:
    """True se o texto parseia inteiro como comida (todos os itens reconhecidos).

    Pré-checagem barata: sem parte começando com dígito não é refeição — nem
    carrega a base de alimentos.
    """
    parts = [p.strip() for p in re.split(r"[,\n]", text) if p.strip()]
    if not parts or not any(p[0].isdigit() for p in parts):
        return False
    try:
        parsed = parse_meal(text, load_food_db(db_path), fuzzy=False)
    except Exception:  # noqa: BLE001 — na dúvida, segue o fluxo normal (coach)
        return False
    items = parsed.get("items", [])
    return bool(items) and all(it.get("recognized") for it in items)


async def on_text_nutrition(update, context):
    """Texto solto fora de thread /ask: macros pendentes > alimentos da sessão /comi."""
    # nome pendente após foto do rótulo: texto = nome do alimento -> cadastra com os macros lidos.
    pend = context.user_data.get("awaiting_food_name")
    if pend:
        nome = update.message.text.strip()
        context.user_data.pop("awaiting_food_name", None)
        store.add_custom_food(context.bot_data["db_path"], nome, pend["base_unit"],
                              pend.get("porcao_g"), pend["kcal"], pend["p"], pend["c"],
                              pend["g"], source="foto")
        await update.message.reply_text(
            f"Cadastrei {nome} (rótulo). Agora manda a quantidade — ex.: 30g {nome}.")
        return
    name = context.user_data.get("awaiting_manual")
    if not name:
        # sessão /comi ativa com refeição escolhida: texto = alimentos a somar.
        comi = context.user_data.get("comi")
        if comi and comi.get("meal"):
            await _comi_add_foods(update, context, update.message.text.strip())
        return
    macros = parse_manual_macros(update.message.text)
    if not macros:
        await update.message.reply_text("Formato: kcal proteína carbo gordura (ex.: 120 24 3 1.5)")
        return
    context.user_data["pending_custom"] = {
        "name": name,
        "base_unit": "100g",
        "porcao_g": None,
        "kcal": macros["kcal"],
        "p": macros["p"],
        "c": macros["c"],
        "g": macros["g"],
    }
    context.user_data.pop("awaiting_manual", None)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ salvar", callback_data="nut:foodsave"),
        InlineKeyboardButton("✏️ corrigir", callback_data="nut:manual"),
    ]])
    await update.message.reply_text(
        f"{name}: {round(macros['kcal'])} kcal · P {macros['p']:.0f} · "
        f"C {macros['c']:.0f} · G {macros['g']:.0f}. Confere?",
        reply_markup=kb,
    )


async def cmd_cancelar(update, context):
    if not _authorized(update, context):
        return
    for k in ("pending_meal", "pending_food", "pending_custom", "awaiting_manual",
              "comi", "comi_foto", "awaiting_food_name"):
        context.user_data.pop(k, None)
    await update.message.reply_text("Ok, cancelei o registro em andamento.")


# ── nutrição: peso semanal + progresso ─────────────────────────────────────────

async def cmd_macros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = dt.date.today().isoformat()
    panel = today_panel(context.bot_data["db_path"], _profile(context), day)
    await update.message.reply_text(
        format_macros_today(panel["today"]), parse_mode="Markdown"
    )


async def cmd_peso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = " ".join(context.args) if context.args else ""
    kg = parse_peso_arg(arg)
    if kg is None:
        await update.message.reply_text("Uso: /peso 107.4")
        return
    today = dt.date.today().isoformat()
    store.add_weight(context.bot_data["db_path"], today, kg, source="manual")
    await update.message.reply_text(f"Peso salvo: {kg:.1f} kg ✅")


def _week_context(db_path, profile):
    """Junta pesos, dias da semana (p/kcal/training) e cfg pro relatório de progresso."""
    cfg = nutrition_config(profile)
    cfg["kcal_adjust"] = store.get_kcal_adjust(db_path)
    ws = [w["kg"] for w in store.get_weights(db_path)]
    today = dt.date.today()
    dates = [(today - dt.timedelta(days=i)).isoformat() for i in range(1, 8)]
    tots = store.week_totals(db_path, dates)
    week_days = []
    for d, t in zip(dates, tots):
        plan = store.get_day_plan(db_path, d) or {}
        training = bool(plan.get("vai_treinar") or plan.get("vai_correr"))
        week_days.append({"p": t["p"], "kcal": t["kcal"], "training": training})
    prev_bf = float(profile.get("percentual_gordura") or 30)
    prev_weight = float(profile.get("peso_kg") or (ws[0] if ws else 108))
    return ws, week_days, cfg, prev_bf, prev_weight


async def cmd_progresso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db_path = context.bot_data["db_path"]
    ws, week_days, cfg, prev_bf, prev_weight = _week_context(db_path, _profile(context))
    rep = build_progress_report(ws, week_days, cfg, prev_bf, prev_weight)
    markup = None
    if rep["proposal"]["action"] in ("cut", "add"):
        delta = rep["proposal"]["delta_kcal"]
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ aplicar", callback_data=f"adj:apply:{delta}"),
            InlineKeyboardButton("✋ manter", callback_data="adj:hold"),
        ]])
    await update.message.reply_text(rep["text"], parse_mode="Markdown", reply_markup=markup)


async def on_adjust_button(update, context):
    q = update.callback_query
    await q.answer()
    db_path = context.bot_data["db_path"]
    if q.data.startswith("adj:apply:"):
        delta = int(q.data.split(":")[-1])
        novo = store.get_kcal_adjust(db_path) + delta
        store.set_kcal_adjust(db_path, novo)
        await q.edit_message_text(f"Alvo ajustado em {delta:+d} kcal. Novo ajuste: {novo:+d}. ✅")
    else:
        await q.edit_message_text("Alvo mantido. ✋")
