import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import bot.handlers_nutrition as hn
import src.nutrition.store as store
from src.history_db import HistoryDB
from src.nutrition.food_db import FoodDB


def _fdb():
    return FoodDB("tests/fixtures/taco_min.csv")


def _db(tmp_path):
    p = str(tmp_path / "h.db")
    HistoryDB(p)
    return p


def _ctx(tmp_path):
    c = MagicMock()
    c.bot_data = {"anthropic": None, "db": MagicMock(), "db_path": _db(tmp_path),
                  "client": MagicMock(), "cfg": MagicMock(chat_id=1)}
    c.user_data = {}
    return c


def _update(text):
    u = MagicMock()
    u.effective_chat.id = 1
    u.message.text = text
    u.message.reply_text = AsyncMock()
    return u


def _cb(data):
    q = MagicMock()
    q.data = data
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    u = MagicMock(callback_query=q)
    u.effective_chat.id = 1
    return u, q


def _botoes(kb):
    return [b.callback_data for row in kb.inline_keyboard for b in row]


def test_combo_salvar_reconhecido_pede_confirmacao(tmp_path):
    c = _ctx(tmp_path)
    u = _update("/combo salvar café: 100g arroz cozido")
    with patch("bot.handlers_nutrition.load_food_db", return_value=_fdb()):
        asyncio.run(hn.cmd_combo(u, c))
    assert c.user_data["pending_combo"] == {"name": "café",
                                            "items_text": "100g arroz cozido"}
    txt = u.message.reply_text.call_args[0][0]
    assert "total" in txt.lower()
    kb = u.message.reply_text.call_args[1]["reply_markup"]
    assert "cmb:save" in _botoes(kb) and "cmb:cancel" in _botoes(kb)


def test_combo_salvar_item_desconhecido_recusa(tmp_path):
    c = _ctx(tmp_path)
    u = _update("/combo salvar café: 100g unicornio grelhado")
    with patch("bot.handlers_nutrition.load_food_db", return_value=_fdb()):
        asyncio.run(hn.cmd_combo(u, c))
    assert "pending_combo" not in c.user_data
    txt = u.message.reply_text.call_args[0][0]
    assert "unicornio" in txt.lower()


def test_combo_salvar_sem_dois_pontos_mostra_uso(tmp_path):
    c = _ctx(tmp_path)
    u = _update("/combo salvar café sem separador")
    asyncio.run(hn.cmd_combo(u, c))
    txt = u.message.reply_text.call_args[0][0]
    assert "/combo salvar" in txt


def test_combo_lista_vazia_explica(tmp_path):
    c = _ctx(tmp_path)
    u = _update("/combo")
    asyncio.run(hn.cmd_combo(u, c))
    txt = u.message.reply_text.call_args[0][0]
    assert "salvar" in txt.lower()


def test_combo_lista_botoes_com_resumo(tmp_path):
    c = _ctx(tmp_path)
    store.save_combo(c.bot_data["db_path"], "café", "100g arroz cozido")
    u = _update("/combo")
    with patch("bot.handlers_nutrition.load_food_db", return_value=_fdb()):
        asyncio.run(hn.cmd_combo(u, c))
    kb = u.message.reply_text.call_args[1]["reply_markup"]
    botoes = _botoes(kb)
    assert "cmb:log:café" in botoes and "cmb:delmode" in botoes
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert any("kcal" in lb for lb in labels)


def test_botao_save_persiste(tmp_path):
    c = _ctx(tmp_path)
    c.user_data["pending_combo"] = {"name": "café", "items_text": "100g arroz cozido"}
    u, q = _cb("cmb:save")
    asyncio.run(hn.on_combo_button(u, c))
    combos = store.get_combos(c.bot_data["db_path"])
    assert combos[0]["name"] == "café"
    assert "pending_combo" not in c.user_data


def test_botao_log_pergunta_refeicao(tmp_path):
    c = _ctx(tmp_path)
    store.save_combo(c.bot_data["db_path"], "café", "100g arroz cozido")
    u, q = _cb("cmb:log:café")
    asyncio.run(hn.on_combo_button(u, c))
    assert c.user_data["combo_log"] == "café"
    kb = q.edit_message_text.call_args[1]["reply_markup"]
    assert any(b.startswith("cmb:meal:") for b in _botoes(kb))


def test_botao_meal_grava_no_diario(tmp_path):
    c = _ctx(tmp_path)
    db_path = c.bot_data["db_path"]
    store.save_combo(db_path, "café", "100g arroz cozido")
    c.user_data["combo_log"] = "café"
    u, q = _cb("cmb:meal:café da manhã")
    with patch("bot.handlers_nutrition.load_food_db", return_value=_fdb()):
        asyncio.run(hn.on_combo_button(u, c))
    import datetime as dt
    t = store.day_totals(db_path, dt.date.today().isoformat())
    assert t["kcal"] > 0
    assert "combo_log" not in c.user_data
    txt = q.edit_message_text.call_args[0][0]
    assert "✅" in txt


def test_botao_meal_item_fora_da_base_nao_grava(tmp_path):
    c = _ctx(tmp_path)
    db_path = c.bot_data["db_path"]
    store.save_combo(db_path, "café", "100g unicornio grelhado")
    c.user_data["combo_log"] = "café"
    u, q = _cb("cmb:meal:janta")
    with patch("bot.handlers_nutrition.load_food_db", return_value=_fdb()):
        asyncio.run(hn.on_combo_button(u, c))
    import datetime as dt
    t = store.day_totals(db_path, dt.date.today().isoformat())
    assert t["kcal"] == 0


def test_botao_delmode_e_del(tmp_path):
    c = _ctx(tmp_path)
    db_path = c.bot_data["db_path"]
    store.save_combo(db_path, "café", "100g arroz cozido")
    u, q = _cb("cmb:delmode")
    asyncio.run(hn.on_combo_button(u, c))
    kb = q.edit_message_text.call_args[1]["reply_markup"]
    assert "cmb:del:café" in _botoes(kb)
    u2, q2 = _cb("cmb:del:café")
    asyncio.run(hn.on_combo_button(u2, c))
    assert store.get_combos(db_path) == []


# ── /dieta redesenhado: texto de decisão + PNG ─────────────────────────────────

def test_dieta_manda_texto_e_foto(tmp_path):
    c = _ctx(tmp_path)
    c.bot_data["profile"] = {"peso_kg": 108, "percentual_gordura": 30}
    db_path = c.bot_data["db_path"]
    store.save_meal_items(db_path, __import__("datetime").date.today().isoformat(),
                          "almoço",
                          [{"recognized": True, "food": "peito de frango grelhado",
                            "grams": 150, "kcal": 239, "p": 46, "c": 0, "g": 5}])
    u = _update("/dieta")
    u.message.reply_photo = AsyncMock()
    with patch("bot.handlers_nutrition.load_food_db", return_value=_fdb()):
        asyncio.run(hn.cmd_dieta(u, c))
    txt = u.message.reply_text.call_args[0][0]
    assert "faltam" in txt.lower()
    assert "almoço" in txt.lower()
    u.message.reply_photo.assert_awaited_once()
