_DIAS = {"seg", "ter", "qua", "qui", "sex", "sab", "dom"}
_ACENTOS = str.maketrans("áâãàéêíóôõúç", "aaaaeeiooouc")


def _norm_dia(tok: str) -> str:
    return tok.strip().lower().translate(_ACENTOS)[:3]


def _tipo(tok: str):
    t = tok.strip().lower().translate(_ACENTOS)
    if t.startswith("cor"):
        return "corrida"
    if t.startswith("mus") or t.startswith("for"):
        return "musculacao"
    return None


def parse_plan(text: str) -> dict:
    """Parseia a semana colada (1 treino por linha: 'dia tipo descrição').
    Linha sem dia/tipo reconhecível é ignorada. A linha do comando /plano é ignorada."""
    corrida, musculacao = [], []
    for line in (text or "").splitlines():
        parts = line.split()
        if parts and parts[0].lower().startswith("/plano"):
            parts = parts[1:]
        if len(parts) < 2:
            continue
        if _norm_dia(parts[0]) not in _DIAS:
            continue
        tipo = _tipo(parts[1])
        if tipo is None:
            continue
        item = {"dia": parts[0], "descricao": " ".join(parts[2:]).strip()}
        (corrida if tipo == "corrida" else musculacao).append(item)
    return {"corrida": corrida, "musculacao": musculacao}
