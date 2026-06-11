import json
from src.ai_coach import ask_coach


class TrainingPlanner:
    def generate_weekly_plan(self, context: dict) -> list:
        """
        Generate a 7-day training plan using Sonnet (depth='deep').

        CONSTRAINTS:
        - Minimum 3 run days per week (HARD CONSTRAINT)
        - Maximum 5 training days (2 rest/recovery days)
        - Strength training on low aerobic load days
        - If poor sleep (debt > 1h) or Body Battery < 40: reduce intensity
        - Consider recent activities to avoid overload
        - Running and strength training NOT on the same day

        Args:
            context: dict with resting_hr_avg_7d, morning_battery_avg, sleep_debt_hours, etc.

        Returns:
            list of 7 dicts with keys: dia, tipo, descricao, duracao, intensidade

        Raises:
            ValueError: if generated plan has fewer than 3 run days
        """
        prompt = """Gere um plano semanal de treino de 7 dias.

REGRAS OBRIGATÓRIAS:
- Mínimo 3 dias de corrida por semana (HARD CONSTRAINT)
- Máximo 5 dias de treino (2 dias de descanso/recuperação)
- Musculação nos dias de menor carga aeróbica
- Se sono ruim (debt > 1h) ou Body Battery < 40: reduza intensidade do dia
- Considere atividades recentes para evitar sobrecarga
- Corrida e musculação NÃO no mesmo dia

Retorne EXATAMENTE este JSON (array de 7 objetos, sem markdown, sem texto extra):
[
  {"dia": "Segunda", "tipo": "corrida|musculação|descanso", "descricao": "...", "duracao": <minutos>, "intensidade": "leve|moderada|alta|nenhuma"},
  ...
]"""

        for attempt in range(3):
            raw = ask_coach(prompt, context, depth="deep")
            cleaned = raw.strip()

            # Remove markdown code blocks if present
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]

            plan = json.loads(cleaned)

            # Validate: must have at least 3 run days
            run_days = sum(1 for d in plan if d.get("tipo") == "corrida")
            if run_days >= 3:
                return plan

        raise ValueError(f"Plan failed to include ≥3 run days after 3 attempts.")
