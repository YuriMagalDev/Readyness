import json
import os
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"

def _load_athlete_profile() -> dict:
    path = Path("athlete_profile.json")
    if not path.exists():
        raise FileNotFoundError("athlete_profile.json not found. Create it from the spec.")
    return json.loads(path.read_text(encoding="utf-8"))

def ask_coach(prompt: str, context: dict, depth: str = "quick") -> str:
    """
    depth='quick' → Haiku  (análises rápidas, < 300 tokens)
    depth='deep'  → Sonnet (planos, análises multi-etapa)
    """
    model = HAIKU if depth == "quick" else SONNET
    profile = _load_athlete_profile()

    system = f"""Você é um coach de saúde e treino pessoal para {profile['nome']}.

PERFIL DO ATLETA:
{json.dumps(profile, ensure_ascii=False, indent=2)}

CONTEXTO ATUAL:
{json.dumps(context, ensure_ascii=False, indent=2)}

Responda em português. Seja direto e prático."""

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=model,
        max_tokens=1024 if depth == "quick" else 2048,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
