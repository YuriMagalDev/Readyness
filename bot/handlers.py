import datetime as dt
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot import core, messages
from bot.checkin import CHECKINS, scale_keyboard, parse_callback, prompt_text
from bot.charts import recovery_chart_png, nutrition_chart_png, nutrition_panel_png
from bot.nutrition import (
    load_food_db, today_panel, resolve_unknowns,
    parse_peso_arg, build_progress_report,
)
from src.nutrition.config import nutrition_config
from bot.nutrition_format import format_meal_confirm, format_nutri_context, format_macros_today
from bot.runs import filter_runs
from src.services_core import save_checkin, build_trends, build_run_detail
from src.extractors import activity_from_garmin
from src.plan_parser import parse_plan
from src.plan_tracker import match_plan, week_start_of
from src.readiness_score import compute_readiness
from src.metric_reader import context_from_metrics
from src.nutrition.meal_parser import parse_meal
from src.nutrition.label_vision import extract_label
import src.nutrition.store as store
import bot.ask as ask
from bot.ask import build_run_context as ask_build_run, build_general_context as ask_build_general
from src.ai_coach import ask_coach


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


def _authorized(update: Update, context) -> bool:
    cfg = context.bot_data["cfg"]
    chat = update.effective_chat
    return chat is not None and chat.id == cfg.chat_id


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await update.message.reply_text(
        "Readiness bot. Comandos:\n"
        "/saldo — saldo do dia\n/insights — leitura da IA\n"
        "/checkin — responder hidratação/energia/dor/alimentação\n"
        "/semana — resumo 7d\n/mes — resumo 30d\n"
        "/plano — registrar/ver o plano da semana\n"
        "/comi — registrar refeição\n"
        "/dieta — macros e energia do dia (gráfico)\n"
        "/macros — macros de hoje em texto (consumido vs alvo)\n"
        "/ask — conversar com o coach (corrida ou assunto geral)\n"
        "/progresso — tendência de peso, BF estimado, ajuste\n"
        "/ref — refeições de hoje (editar/apagar item)\n"
        "/cancelar — cancelar registro em andamento"
    )


async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    day = dt.date.today().isoformat()
    # métricas/sono dependem do Garmin (pode 429 / sem sync); veredito vem do DB e sempre sai
    try:
        ctx = core.load_context(client)
        met, sleep = core.collect_metrics(ctx), core.sleep_view(ctx)
    except Exception:  # noqa: BLE001
        met, sleep = {}, {}
    try:
        analysis = core.daily_analysis(db, day)
        txt = messages.format_saldo(analysis["veredito"], met, sleep=sleep)
        # nutrição = contexto informativo (não muda o veredito); nunca derruba o /saldo
        try:
            panel = today_panel(context.bot_data["db_path"], _profile(context), day)
            nutri = format_nutri_context(panel["yesterday"])
            if nutri:
                txt += "\n\n" + nutri
        except Exception:  # noqa: BLE001 — sem dados de nutrição: saldo segue normal
            pass
        await update.message.reply_text(txt, parse_mode=messages.PARSE_MODE)
    except Exception as e:  # noqa: BLE001
        await update.message.reply_text(f"Não consegui montar o saldo agora ({e}).")


async def cmd_insights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    day = dt.date.today().isoformat()
    try:
        analysis = core.daily_analysis(db, day)
        txt = messages.format_insights(analysis["insights"])
    except Exception:  # noqa: BLE001
        txt = messages.format_insights([])
    await update.message.reply_text(txt)


async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    day = dt.date.today().isoformat()
    for c in CHECKINS:
        await update.message.reply_text(prompt_text(c), reply_markup=scale_keyboard(c["key"], day))


async def on_checkin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    q = update.callback_query
    parsed = parse_callback(q.data)
    if not parsed:
        await q.answer("inválido")
        return
    key, val, day = parsed
    # grava sempre no dia do check-in (vindo no callback), não no dia do clique
    save_checkin(context.bot_data["db"], {key: val}, today=dt.date.fromisoformat(day))
    label = next((c["label"] for c in CHECKINS if c["key"] == key), key)
    await q.answer("anotado")
    await q.edit_message_text(f"{label}: {val} ✓")


async def _send_trends(update, context, period: int, titulo: str):
    db = context.bot_data["db"]
    trends = build_trends(db, period=period)
    png = recovery_chart_png(trends, titulo=titulo)
    legenda = messages.format_insights(
        [{"texto": t, "metricas_usadas": []} for t in trends.get("insights", [])]
    )
    await update.message.reply_photo(photo=png, caption=legenda[:1024] or titulo)


async def cmd_semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await _send_trends(update, context, 7, "Semana")


async def cmd_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    await _send_trends(update, context, 30, "Mês")


def _run_button_label(raw: dict) -> str:
    data = (raw.get("startTimeLocal") or "")[:10]
    nome = raw.get("activityName") or "Corrida"
    dist = raw.get("distance")
    km = f"{dist / 1000:.1f}km" if dist else "—"
    return f"{data} · {nome} · {km}"


async def cmd_atividades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    client = context.bot_data["client"]
    try:
        runs = filter_runs(client.get_activities(7, fresh=True))[:8]   # últimas 8 corridas
    except Exception:  # noqa: BLE001
        await update.message.reply_text("Não consegui buscar suas atividades agora.")
        return
    if not runs:
        await update.message.reply_text("Nenhuma corrida recente encontrada.")
        return
    db = context.bot_data["db"]
    for r in runs:
        db.upsert_activity(activity_from_garmin(r))
    teclado = [
        [InlineKeyboardButton(_run_button_label(r), callback_data=f"act:{r['activityId']}")]
        for r in runs
    ]
    await update.message.reply_text(
        "Escolha uma corrida pra ver o insight:", reply_markup=InlineKeyboardMarkup(teclado)
    )


async def cmd_plano(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    db = context.bot_data["db"]
    today = dt.date.today()
    week_start = week_start_of(today)
    texto = update.message.text or ""
    corpo = "\n".join(texto.splitlines()[1:]).strip()  # linhas após o /plano

    if corpo:
        plan = parse_plan(texto)
        if not plan["corrida"] and not plan["musculacao"]:
            await update.message.reply_text(
                "Formato inválido. Ex:\n/plano\nseg corrida 40min\nter musculacao superior")
            return
        db.upsert_plan(week_start, plan, dt.datetime.now().isoformat(timespec="seconds"))
        await update.message.reply_text(
            f"Plano salvo: {len(plan['corrida'])} corridas, {len(plan['musculacao'])} musculações.")

    stored = db.get_plan(week_start)
    if stored is None:
        await update.message.reply_text(
            "Nenhum plano esta semana. Registre colando:\n"
            "/plano\nseg corrida 40min\nter musculacao superior")
        return

    plan = stored["plan"]
    acts = db.get_activities(week_start, today.isoformat())
    matched = match_plan(plan, acts, today, week_start)
    try:
        ctx = context_from_metrics(db, today.isoformat())
        score, acwr = compute_readiness(ctx)["score"], ctx.get("acwr")
    except Exception:  # noqa: BLE001 — prontidão é enfeite do cabeçalho; plano sai mesmo sem ela
        score, acwr = None, None
    await update.message.reply_text(
        messages.format_plan(matched, score, acwr), parse_mode=messages.PARSE_MODE)


def _profile(context):
    return context.bot_data.get("profile") or {}


async def cmd_comi(update, context):
    if not _authorized(update, context):
        return
    db_path = context.bot_data["db_path"]
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
    await update.message.reply_text(format_meal_confirm(parsed), reply_markup=kb)


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


async def on_text_macros(update, context):
    """Roteia texto solto: thread /ask ativa > macros pendentes > alimentos da sessão /comi."""
    if not _authorized(update, context):
        return
    # thread /ask ativa tem prioridade sobre o fluxo de macros
    if ask.is_active(context.user_data):
        await _handle_ask_turn(update, context)
        return
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


async def on_activity_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    try:
        aid = int(q.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await q.edit_message_text("Atividade inválida.")
        return
    db = context.bot_data["db"]
    client = context.bot_data["client"]
    try:
        detail = build_run_detail(db, client, aid)
    except Exception:  # noqa: BLE001
        await q.edit_message_text("Não consegui analisar essa corrida agora.")
        return
    await q.edit_message_text(
        messages.format_activity(detail["activity"], detail["insight"]),
        parse_mode=messages.PARSE_MODE,
    )


# ── nutrição: peso semanal + progresso ─────────────────────────────────────────

async def cmd_macros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = dt.date.today().isoformat()
    panel = today_panel(context.bot_data["db_path"], _profile(context), day)
    await update.message.reply_text(
        format_macros_today(panel["today"]), parse_mode="Markdown"
    )


# ── /ask: coach conversacional (corrida ou assunto geral) ──────────────────────

_ASK_KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("🏃 Corrida", callback_data="ask:run"),
    InlineKeyboardButton("💬 Outro assunto", callback_data="ask:geral"),
]])
_ASK_FIM_KB = InlineKeyboardMarkup([[
    InlineKeyboardButton("✋ finalizar", callback_data="ask:fim")]])


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update, context):
        return
    if context.bot_data.get("anthropic") is None:
        await update.message.reply_text("🤖 Coach indisponível agora (sem ANTHROPIC_API_KEY).")
        return
    await update.message.reply_text("Sobre o quê? 👇", reply_markup=_ASK_KB)


async def on_ask_button(update, context):
    if not _authorized(update, context):
        return
    q = update.callback_query
    await q.answer()
    data = q.data
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
    pergunta = update.message.text.strip()
    ask.append_user(context.user_data, pergunta)
    try:
        resp = ask_coach(ask.history(context.user_data),
                         ask.get_context(context.user_data), depth="deep",
                         extra_system=_ASK_STYLE)
    except Exception:  # noqa: BLE001 — mantém a thread aberta pra nova tentativa
        logging.exception("ask_coach falhou no /ask")
        # remove a pergunta que não foi respondida do histórico
        ask.pop_last(context.user_data)
        await update.message.reply_text("Não consegui responder agora, tenta de novo.")
        return
    ask.append_assistant(context.user_data, resp)
    pedacos = _split_message(resp)
    for pedaco in pedacos[:-1]:
        await update.message.reply_text(pedaco)
    await update.message.reply_text(pedacos[-1], reply_markup=_ASK_FIM_KB)


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
