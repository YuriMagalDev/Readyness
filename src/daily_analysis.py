import json
import datetime as _dt
from datetime import date
from src.ai_coach import ask_coach
from src.insight_engine import _parse_json
from src.metric_reader import read_metrics, context_from_metrics
from src.health_monitor import HealthMonitor


class DailyAnalysis:
    def __init__(self, db=None):
        self.db = db

    def _flatten(self, metrics: dict) -> dict:
        """metric_key -> cell, só métricas com valor (status != ausente)."""
        flat = {}
        for cells in metrics["dominios"].values():
            for c in cells:
                if c["status"] != "ausente":
                    flat[c["key"]] = c
        return flat

    def _insights(self, metrics: dict, force: bool = False) -> list:
        key = f"daily_v2:{metrics['date']}"
        if self.db is not None and not force:
            hit = self.db.get_insight("daily_v2", key)
            if hit is not None:
                return hit

        flat = self._flatten(metrics)
        lista = [{"key": k, "label": c["label"], "valor": c["value"], "status": c["status"]}
                 for k, c in flat.items()]
        prompt = f"""Gere 2-5 observações curtas (1 frase cada) sobre prontidão/recuperação/treino,
com base SOMENTE nas métricas abaixo. Cite só as keys fornecidas.

Métricas: {json.dumps(lista, ensure_ascii=False)}

Retorne EXATAMENTE este JSON:
{{"insights": [{{"texto": "...", "metricas_usadas": ["key1", "key2"]}}]}}"""
        data = _parse_json(ask_coach(prompt, {}, depth="quick"))
        if not data or not isinstance(data.get("insights"), list):
            return []

        result = []
        for ins in data["insights"]:
            texto = (ins or {}).get("texto")
            keys = (ins or {}).get("metricas_usadas") or []
            fontes = []
            for k in keys:
                c = flat.get(k)
                if c is None:
                    continue
                fontes.append({"key": k, "label": c["label"], "valor": c["value"],
                               "unidade": c["unidade"], "status": c["status"]})
            if texto and fontes:
                result.append({"texto": texto, "metricas_usadas": fontes})

        if self.db is not None and result:
            self.db.set_insight("daily_v2", key, result, date.today().isoformat())
        return result

    def build(self, date_str: str, today: _dt.date = None, force: bool = False) -> dict:
        today = today or _dt.date.today()
        metrics = read_metrics(self.db, date_str, today=today)
        context = context_from_metrics(self.db, date_str, today=today)
        veredito = HealthMonitor().verdict(context)
        insights = self._insights(metrics, force=force)
        return {"date": date_str, "veredito": veredito, "insights": insights}
