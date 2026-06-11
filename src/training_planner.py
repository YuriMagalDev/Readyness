import json
from src.ai_coach import ask_coach


class TrainingPlanner:
    def generate_weekly_plan(self, context: dict) -> dict:
        """
        Gera plano semanal via Sonnet (depth='deep') em DUAS grades.

        CONSTRAINTS:
        - Mínimo 3 dias de corrida por semana (HARD CONSTRAINT)
        - Máximo 5 dias com treino (corrida e/ou musculação)
        - Corrida e musculação PODEM cair no mesmo dia
        - Se sono ruim (debt > 1h) ou Body Battery < 40: reduza intensidade
        - Considere atividades recentes para evitar sobrecarga

        Returns:
            dict {"corrida": [...], "musculacao": [...]}
            cada item: {dia, descricao, duracao, intensidade}

        Raises:
            ValueError: se plano gerado tiver menos de 3 dias de corrida após 3 tentativas
        """
        prompt = """Gere um plano semanal de treino dividido em DUAS grades separadas:
uma para CORRIDA e uma para MUSCULAÇÃO.

REGRAS OBRIGATÓRIAS:
- Mínimo 3 dias de corrida por semana (HARD CONSTRAINT)
- Máximo 5 dias com algum treino na semana (deixe 2 dias livres)
- Corrida e musculação PODEM ocorrer no mesmo dia
- Musculação preferencialmente em dias de corrida leve ou sem corrida
- Se sono ruim (debt > 1h) ou Body Battery < 40: reduza intensidade do dia
- Considere atividades recentes para evitar sobrecarga

Retorne EXATAMENTE este JSON (sem markdown, sem texto extra):
{
  "corrida": [
    {"dia": "Segunda", "descricao": "...", "duracao": <minutos>, "intensidade": "leve|moderada|alta"}
  ],
  "musculacao": [
    {"dia": "Segunda", "descricao": "...", "duracao": <minutos>, "intensidade": "leve|moderada|alta"}
  ]
}"""

        for _ in range(3):
            raw = ask_coach(prompt, context, depth="deep")
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]

            plan = json.loads(cleaned)
            corrida = plan.get("corrida", [])
            if len(corrida) >= 3:
                return {"corrida": corrida, "musculacao": plan.get("musculacao", [])}

        raise ValueError("Plan failed to include ≥3 run days after 3 attempts.")
