import json
from src.ai_coach import ask_coach

HR_ALERT_BPM = 5
BATTERY_LOW = 25
SLEEP_DEBT_THRESHOLD = 2.0

class HealthMonitor:
    def _evaluate_rules(self, context: dict) -> dict:
        hr_avg = context.get("resting_hr_avg_7d", 0)
        hr_today = context.get("resting_hr_today", hr_avg)
        battery = context.get("morning_battery_avg", 100)
        sleep_debt = context.get("sleep_debt_hours", 0)

        if hr_today >= hr_avg + HR_ALERT_BPM:
            return {
                "status": "vermelho",
                "motivo": f"FC repouso hoje ({hr_today} bpm) está {hr_today - hr_avg} bpm acima da média de 7 dias ({hr_avg} bpm)",
                "recomendacao": "Evite treinos intensos. Priorize recuperação.",
            }
        if battery < BATTERY_LOW:
            return {
                "status": "amarelo",
                "motivo": f"Body Battery matinal baixo ({battery})",
                "recomendacao": "Treino leve ou descanso ativo.",
            }
        if sleep_debt >= SLEEP_DEBT_THRESHOLD:
            return {
                "status": "amarelo",
                "motivo": f"Dívida de sono acumulada: {sleep_debt}h na semana",
                "recomendacao": "Tente dormir mais esta noite. Reduza intensidade hoje.",
            }
        return {
            "status": "verde",
            "motivo": "Métricas normais",
            "recomendacao": "Pode treinar conforme planejado.",
        }

    def check(self, context: dict) -> dict:
        rule_result = self._evaluate_rules(context)

        prompt = f"""Com base nas métricas abaixo, avalie a prontidão para treino hoje.
Retorne EXATAMENTE este JSON (sem markdown, sem texto extra):
{{"status": "verde|amarelo|vermelho", "motivo": "...", "recomendacao": "..."}}

Avaliação preliminar das regras: {json.dumps(rule_result, ensure_ascii=False)}"""

        raw = ask_coach(prompt, context, depth="quick")
        try:
            result = json.loads(raw.strip())
            if result.get("status") not in ("verde", "amarelo", "vermelho"):
                return rule_result
            return result
        except json.JSONDecodeError:
            return rule_result
