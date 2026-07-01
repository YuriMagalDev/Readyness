import json
import os
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-5"

def _load_athlete_profile() -> dict:
    path = Path("athlete_profile.json")
    if not path.exists():
        raise FileNotFoundError("athlete_profile.json not found. Create it from the spec.")
    return json.loads(path.read_text(encoding="utf-8"))

def ask_coach(messages, context: dict, depth: str = "quick", extra_system: str = None) -> str:
    """
    messages: str (uma pergunta) OU list[{"role","content"}] (thread com histórico).
    depth='quick' → Haiku ; depth='deep' → Sonnet.
    extra_system: instrução extra de estilo (ex.: conversa /ask) — não afeta outros callers.
    """
    model = HAIKU if depth == "quick" else SONNET
    profile = _load_athlete_profile()

    profile_block = (
        f"Você é um coach de saúde e treino pessoal para {profile['nome']}.\n\n"
        f"PERFIL DO ATLETA:\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        "Responda em português. Seja direto e prático."
    )
    context_block = f"CONTEXTO ATUAL:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    system = [
        {"type": "text", "text": profile_block, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": context_block},
    ]
    if extra_system:
        system.append({"type": "text", "text": extra_system})

    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=model,
        max_tokens=1024 if depth == "quick" else 2048,
        system=system,
        messages=messages,
    )
    # Sonnet 5 emite ThinkingBlock antes do texto (extended thinking on por padrão).
    # Pega o primeiro bloco que tem texto; ignora blocos de raciocínio.
    for block in message.content:
        text = getattr(block, "text", None)
        if text is not None:
            return text
    return ""
