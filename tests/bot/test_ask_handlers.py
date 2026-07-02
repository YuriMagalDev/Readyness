import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import bot.handlers as handlers
import bot.ask as ask
from src.nutrition.food_db import FoodDB


def _fdb():
    return FoodDB("tests/fixtures/taco_min.csv")


def _ctx(anthropic="client"):
    c = MagicMock()
    c.bot_data = {"anthropic": anthropic, "db": MagicMock(), "db_path": "h.db",
                  "client": MagicMock(), "cfg": MagicMock(chat_id=1)}
    c.user_data = {}
    return c


def _update(chat_id=1):
    u = MagicMock()
    u.effective_chat.id = chat_id
    u.message.reply_text = AsyncMock()
    return u


def test_cmd_ask_sem_api_key_avisa():
    u, c = _update(), _ctx(anthropic=None)
    asyncio.run(handlers.cmd_ask(u, c))
    txt = u.message.reply_text.call_args[0][0]
    assert "indispon" in txt.lower()
    assert ask.is_active(c.user_data) is False


def test_cmd_ask_sem_perfil_avisa_claro():
    u, c = _update(), _ctx()
    with patch("bot.handlers_ask._profile_file_exists", return_value=False):
        asyncio.run(handlers.cmd_ask(u, c))
    txt = u.message.reply_text.call_args[0][0]
    assert "athlete_profile.json" in txt
    assert ask.is_active(c.user_data) is False


def test_cmd_ask_com_api_mostra_botoes():
    u, c = _update(), _ctx()
    asyncio.run(handlers.cmd_ask(u, c))
    kb = u.message.reply_text.call_args[1]["reply_markup"]
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "ask:run" in datas and "ask:geral" in datas


def test_on_ask_geral_abre_thread():
    c = _ctx()
    q = MagicMock()
    q.data = "ask:geral"
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    u = MagicMock(callback_query=q)
    u.effective_chat.id = 1
    with patch("bot.handlers_ask.ask_build_general", return_value={"readiness": {}}):
        asyncio.run(handlers.on_ask_button(u, c))
    assert ask.is_active(c.user_data) is True
    assert ask.get_context(c.user_data) == {"readiness": {}}


def test_on_ask_fim_fecha_thread():
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={})
    q = MagicMock()
    q.data = "ask:fim"
    q.answer = AsyncMock()
    q.edit_message_reply_markup = AsyncMock()
    q.message.reply_text = AsyncMock()
    u = MagicMock(callback_query=q)
    u.effective_chat.id = 1
    asyncio.run(handlers.on_ask_button(u, c))
    assert ask.is_active(c.user_data) is False
    # tira só o botão (mantém a resposta), não sobrescreve o texto
    q.edit_message_reply_markup.assert_called_once_with(reply_markup=None)


def test_text_thread_ativa_chama_coach():
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={"readiness": {}})
    u = _update()
    u.message.text = "é certo desacelerar no fim?"
    with patch("bot.handlers_ask.ask_coach", return_value="depende do objetivo") as m:
        asyncio.run(handlers.on_text_macros(u, c))
    # histórico acumulou pergunta + resposta
    assert ask.history(c.user_data)[-2:] == [
        {"role": "user", "content": "é certo desacelerar no fim?"},
        {"role": "assistant", "content": "depende do objetivo"},
    ]
    # resposta enviada com botão finalizar
    kb = u.message.reply_text.call_args[1]["reply_markup"]
    assert kb.inline_keyboard[0][0].callback_data == "ask:fim"
    assert m.call_args[1]["depth"] == "deep"


def test_text_sem_thread_nao_chama_coach():
    c = _ctx()
    u = _update()
    u.message.text = "qualquer coisa"
    with patch("bot.handlers_ask.ask_coach") as m:
        asyncio.run(handlers.on_text_macros(u, c))
    m.assert_not_called()


def test_text_thread_coach_falha_mantem_thread():
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={})
    u = _update()
    u.message.text = "pergunta"
    with patch("bot.handlers_ask.ask_coach", side_effect=RuntimeError("timeout")):
        asyncio.run(handlers.on_text_macros(u, c))
    assert ask.is_active(c.user_data) is True   # thread segue aberta
    txt = u.message.reply_text.call_args[0][0]
    assert "tenta de novo" in txt.lower()


def test_thread_ativa_comida_oferece_botoes():
    """Texto que parseia 100% como comida durante thread /ask não vai direto pro coach."""
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={})
    u = _update()
    u.message.text = "100g arroz cozido"
    with patch("bot.handlers_nutrition.load_food_db", return_value=_fdb()), \
         patch("bot.handlers_ask.ask_coach") as m:
        asyncio.run(handlers.on_text_macros(u, c))
    m.assert_not_called()
    kb = u.message.reply_text.call_args[1]["reply_markup"]
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "ask:food:comi" in datas and "ask:food:coach" in datas
    assert c.user_data["ask_food_pending"] == "100g arroz cozido"
    # não entrou no histórico da thread
    assert ask.history(c.user_data) == []


def test_thread_ativa_pergunta_sem_numero_vai_direto_pro_coach():
    """Pergunta normal nem carrega a base de alimentos."""
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={})
    u = _update()
    u.message.text = "é certo desacelerar no fim?"
    with patch("bot.handlers_nutrition.load_food_db") as fdb, \
         patch("bot.handlers_ask.ask_coach", return_value="depende"):
        asyncio.run(handlers.on_text_macros(u, c))
    fdb.assert_not_called()
    assert ask.history(c.user_data)[-1]["content"] == "depende"


def test_thread_ativa_texto_com_numero_mas_nao_comida_vai_pro_coach():
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={})
    u = _update()
    u.message.text = "5km em 30min tá bom?"
    with patch("bot.handlers_nutrition.load_food_db", return_value=_fdb()), \
         patch("bot.handlers_ask.ask_coach", return_value="tá sim") as m:
        asyncio.run(handlers.on_text_macros(u, c))
    m.assert_called_once()


def _cb(data, user_data):
    q = MagicMock()
    q.data = data
    q.answer = AsyncMock()
    q.edit_message_text = AsyncMock()
    q.message.reply_text = AsyncMock()
    u = MagicMock(callback_query=q)
    u.effective_chat.id = 1
    return u, q


def test_askfood_comi_registra_refeicao(tmp_path):
    c = _ctx(anthropic=None)
    c.bot_data["db_path"] = str(tmp_path / "h.db")
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={})
    c.user_data["ask_food_pending"] = "100g arroz cozido"
    u, q = _cb("ask:food:comi", c.user_data)
    with patch("bot.handlers_nutrition.load_food_db", return_value=_fdb()), \
         patch("bot.handlers_ask.ask_coach") as m:
        asyncio.run(handlers.on_ask_button(u, c))
    m.assert_not_called()
    parsed = c.user_data["pending_meal"]
    assert parsed["items"][0]["recognized"] is True
    assert "ask_food_pending" not in c.user_data
    # thread segue aberta pra continuar a conversa depois
    assert ask.is_active(c.user_data) is True


def test_askfood_coach_manda_pro_coach():
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={})
    c.user_data["ask_food_pending"] = "100g arroz cozido"
    u, q = _cb("ask:food:coach", c.user_data)
    with patch("bot.handlers_ask.ask_coach", return_value="ok") as m:
        asyncio.run(handlers.on_ask_button(u, c))
    m.assert_called_once()
    assert ask.history(c.user_data)[-2:] == [
        {"role": "user", "content": "100g arroz cozido"},
        {"role": "assistant", "content": "ok"},
    ]
    assert "ask_food_pending" not in c.user_data


def test_split_message_texto_curto():
    texto = "resposta curta"
    assert handlers._split_message(texto) == [texto]


def test_split_message_texto_longo_varios_pedacos():
    texto = "linha\n" * 2000  # bem maior que o limite
    pedacos = handlers._split_message(texto, limit=4000)
    assert len(pedacos) > 1
    assert all(len(p) <= 4000 for p in pedacos)
    assert "".join(pedacos) == texto


def test_split_message_sem_quebra_de_linha_corta_duro():
    texto = "x" * 9000
    pedacos = handlers._split_message(texto, limit=4000)
    assert all(len(p) <= 4000 for p in pedacos)
    assert "".join(pedacos) == texto


def test_text_thread_resposta_longa_envia_em_pedacos():
    c = _ctx()
    ask.open_thread(c.user_data, mode="geral", run_id=None, context={"readiness": {}})
    u = _update()
    u.message.text = "me conta tudo"
    resposta_longa = "abc " * 2300  # ~9200 chars, > 4000
    with patch("bot.handlers_ask.ask_coach", return_value=resposta_longa):
        asyncio.run(handlers.on_text_macros(u, c))
    chamadas = u.message.reply_text.call_args_list
    assert len(chamadas) > 1
    # só o último pedaço leva o botão de finalizar
    for args, kwargs in chamadas[:-1]:
        assert "reply_markup" not in kwargs
    assert chamadas[-1][1]["reply_markup"] == handlers._ASK_FIM_KB
    # conteúdo reconstruído bate com a resposta original
    texto_reconstruido = "".join(args[0] for args, _ in chamadas)
    assert texto_reconstruido == resposta_longa
    # histórico guarda a resposta completa (não fatiada)
    assert ask.history(c.user_data)[-1] == {"role": "assistant", "content": resposta_longa}
