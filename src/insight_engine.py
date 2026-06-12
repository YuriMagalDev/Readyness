import json
from datetime import date
from src.ai_coach import ask_coach

FALLBACK_TRENDS = ["Dados insuficientes para análise de tendência no momento."]
FALLBACK_DAILY = "Sem análise disponível agora. Siga seu plano normalmente."
FALLBACK_ACTIVITY = "Sem análise detalhada para este treino."


def _parse_json(raw: str):
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        return None


class InsightEngine:
    def __init__(self, db=None):
        self.db = db

    def _cached(self, kind, key, compute, is_fallback, force=False):
        if self.db is not None and not force:
            hit = self.db.get_insight(kind, key)
            if hit is not None:
                return hit
        result = compute()
        if self.db is not None and not is_fallback(result):
            self.db.set_insight(kind, key, result, date.today().isoformat())
        return result

    def trend_insights(self, analytics: dict, period: int = 30, force: bool = False) -> list:
        key = f"trend:{period}:{date.today().isoformat()}"
        def compute():
            prompt = f"""Analise estas tendências de saúde/treino e gere 2-3 observações
curtas e práticas (cada uma 1 frase). Foque no que mudou e no que fazer.

Tendências: {json.dumps(analytics, ensure_ascii=False)}

Retorne EXATAMENTE este JSON: {{"insights": ["...", "..."]}}"""
            data = _parse_json(ask_coach(prompt, {}, depth="quick"))
            if not data or not isinstance(data.get("insights"), list) or not data["insights"]:
                return FALLBACK_TRENDS
            return data["insights"]
        return self._cached("trend", key, compute, lambda r: r == FALLBACK_TRENDS, force=force)

    def daily_insight(self, context: dict, analytics: dict, force: bool = False) -> str:
        key = f"daily:{date.today().isoformat()}"
        def compute():
            prompt = f"""Com base no estado de hoje e nas tendências recentes, dê UMA
recomendação consolidada para hoje (1-2 frases, prática).

Hoje: {json.dumps(context, ensure_ascii=False)}
Tendências: {json.dumps(analytics, ensure_ascii=False)}

Retorne EXATAMENTE este JSON: {{"insight": "..."}}"""
            data = _parse_json(ask_coach(prompt, context, depth="quick"))
            if not data or not data.get("insight"):
                return FALLBACK_DAILY
            return data["insight"]
        return self._cached("daily", key, compute, lambda r: r == FALLBACK_DAILY, force=force)

    def activity_insight(self, activity: dict, splits: list, force: bool = False) -> str:
        def compute():
            prompt = f"""Comente este treino em 1-2 frases: ritmo, FC, consistência dos splits.

Treino: {json.dumps(activity, ensure_ascii=False)}
Splits por km: {json.dumps(splits, ensure_ascii=False)}

Retorne EXATAMENTE este JSON: {{"insight": "..."}}"""
            data = _parse_json(ask_coach(prompt, {}, depth="quick"))
            if not data or not data.get("insight"):
                return FALLBACK_ACTIVITY
            return data["insight"]
        aid = activity.get("activity_id")
        if aid is None:
            return compute()
        key = f"activity:{aid}"
        return self._cached("activity", key, compute, lambda r: r == FALLBACK_ACTIVITY, force=force)
