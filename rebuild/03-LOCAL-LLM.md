# LOCAL LLM — substituir o provedor pago

Decisão: **sem API paga** (sem Anthropic). Roda uma LLM **local**. Toda geração de texto
(insights da análise diária) passa por um único módulo `src/llm.py`, fácil de trocar.

## Runtime recomendado

**Ollama** (mais simples no Windows/desktop): instala, baixa um modelo, expõe HTTP local.
Alternativa: llama.cpp `server` (mesma ideia, endpoint OpenAI-compatível).

- Endpoint Ollama nativo: `POST http://localhost:11434/api/chat` (stream opcional).
- Ou endpoint OpenAI-compatível do Ollama: `POST http://localhost:11434/v1/chat/completions`
  (deixa você usar o SDK `openai` apontando `base_url` pro localhost — útil se quiser).

Modelos (CPU/GPU modesta, PT-BR ok): `llama3.1:8b`, `qwen2.5:7b`, ou um 3B se a máquina for
fraca. Quantização Q4 pra caber na RAM.

## Roteamento de modelo (mesma ideia do design antigo, agora local)

Dois "tamanhos", configuráveis por env:

```
LLM_MODEL_QUICK=qwen2.5:7b      # análise diária / insights (90% das chamadas)
LLM_MODEL_DEEP=llama3.1:8b      # planos / análises profundas (10%)
LLM_BASE_URL=http://localhost:11434
```

`depth="quick"` → modelo rápido; `depth="deep"` → modelo maior. Como é local, "custo" é só
tempo de CPU/GPU — ainda vale separar pra latência.

## Contrato do módulo (`src/llm.py`)

```python
import json, os, requests

BASE = os.getenv("LLM_BASE_URL", "http://localhost:11434")
QUICK = os.getenv("LLM_MODEL_QUICK", "qwen2.5:7b")
DEEP = os.getenv("LLM_MODEL_DEEP", "llama3.1:8b")

def ask_coach(prompt: str, context: dict, depth: str = "quick") -> str:
    model = QUICK if depth == "quick" else DEEP
    system = _system_prompt(context)   # inclui athlete_profile + instruções
    resp = requests.post(f"{BASE}/api/chat", json={
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",            # Ollama: força saída JSON válida
        "options": {"temperature": 0.3},
    }, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"]
```

- `format: "json"` no Ollama faz o modelo devolver JSON parseável — encaixa no contrato dos
  insights (`{"insights":[{"texto","metricas_usadas":[keys]}]}`). Ainda assim, **parse
  tolerante** (modelos pequenos às vezes erram): tente `json.loads`, limpe cercas ```` ```json````,
  e se falhar devolva fallback (lista vazia) — a UI já lida com isso.
- Mantenha a **validação de citações** da Camada 2 (descarta keys inventadas) — ainda mais
  importante com modelo local, que alucina mais.
- Sem prompt caching de provedor (não existe local); cache é o seu, por dia, no SQLite.

## Diferenças vs o design antigo (Anthropic)

| Antes (pago) | Agora (local) |
|---|---|
| `anthropic` SDK, `claude-*` | `requests` → Ollama `/api/chat` |
| `cache_control` (prompt caching) | não existe; confie no cache por-dia em SQLite |
| custo por token | custo = tempo de inferência local |
| modelos haiku/sonnet | `LLM_MODEL_QUICK` / `LLM_MODEL_DEEP` (env) |
| chave de API no `.env` | `LLM_BASE_URL` no `.env`; nada de chave |

## .env alvo

```
GARMIN_EMAIL=...
GARMIN_PASSWORD=...
CACHE_TTL_HOURS=6
LLM_BASE_URL=http://localhost:11434
LLM_MODEL_QUICK=qwen2.5:7b
LLM_MODEL_DEEP=llama3.1:8b
```

## Robustez

- LLM local offline/lenta → `ask_coach` lança/timeout → a análise devolve **insights=[]**, mas
  o **veredito (regra) continua aparecendo**. Treino do dia nunca depende da LLM estar de pé.
- Primeira chamada do dia gera; resto do dia lê do cache. Botão "regenerar" força.
- Teste `llm.py` com o servidor mockado (requests mock) — não dependa da LLM real nos testes.
