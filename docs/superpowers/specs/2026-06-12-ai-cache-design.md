# Spec — Cache de saída de IA + Prompt Caching

**Data:** 2026-06-12
**Objetivo:** Reduzir chamadas e custo da API Anthropic salvando análises já geradas e marcando o prefixo estável do prompt como reaproveitável.

## Problema

Hoje cada carregamento de página chama a API Anthropic do zero:

- `InsightEngine.daily_insight` — recalcula a cada load de Hoje.
- `InsightEngine.trend_insights` — recalcula a cada load de Tendências.
- `InsightEngine.activity_insight` — recalcula a cada abertura do mesmo treino, mesmo sendo passado imutável.

Além disso, todo o `system` prompt (perfil completo + contexto) é reenviado a cada chamada, sem usar prompt caching nativo da Anthropic.

`Cache` (cache.db) existe só para dados do Garmin (TTL). `history_db` (history.db) guarda snapshots/atividades/planos de forma persistente. Nenhum cobre saída de LLM.

## Solução

Duas frentes:

1. **Output cache** — não re-perguntar quando a resposta já é conhecida.
2. **Prompt caching** — marcar o perfil (prefixo estável) com `cache_control` para baratear o input em rajadas.

## 1. Output cache

Nova tabela em `history_db` (persistente, não TTL):

```sql
CREATE TABLE IF NOT EXISTS ai_insights (
  kind TEXT NOT NULL,        -- 'daily' | 'trend' | 'activity'
  cache_key TEXT NOT NULL,   -- ver regras de chave
  payload TEXT NOT NULL,     -- JSON do insight (string ou lista, conforme o tipo)
  created_at TEXT NOT NULL,
  PRIMARY KEY (kind, cache_key)
);
```

### Regras de chave e expiração

| Método | `kind` | `cache_key` | Expiração |
|---|---|---|---|
| `activity_insight` | `activity` | `activity:<id>` | Nunca (passado imutável) |
| `daily_insight` | `daily` | `daily:<today>` | Per-day (1 cálculo/dia) |
| `trend_insights` | `trend` | `trend:<period>:<today>` | Per-day por período |

`<today>` = `date.today().isoformat()`. Per-day significa: primeira chamada do dia computa e grava; chamadas seguintes no mesmo dia reusam. Mudanças intradiárias são tratadas pelo botão de regenerar (seção 2), não automaticamente.

### Métodos novos em HistoryDB

```python
def get_insight(self, kind: str, cache_key: str) -> dict | list | None
def set_insight(self, kind: str, cache_key: str, payload, created_at: str) -> None
def delete_insight(self, kind: str, cache_key: str) -> None
```

`payload` serializado com `json.dumps` na escrita, `json.loads` na leitura.

### InsightEngine

`InsightEngine.__init__(self, db=None)` — recebe `HistoryDB`. Sem `db`, comportamento atual (sempre chama API), para não quebrar testes existentes.

Cada método ganha `force: bool = False`:

```python
def daily_insight(self, context, analytics, force=False):
    key = f"daily:{date.today().isoformat()}"
    if self.db and not force:
        cached = self.db.get_insight("daily", key)
        if cached is not None:
            return cached
    result = ...  # lógica atual (ask_coach + parse + fallback)
    if self.db and result is not FALLBACK_DAILY:  # não cachear fallback
        self.db.set_insight("daily", key, result, date.today().isoformat())
    return result
```

Mesma estrutura para `trend_insights` (key `trend:<period>:<today>`, precisa receber `period`) e `activity_insight` (key `activity:<id>`, nunca expira; só checa existência, ignora data).

**Não cachear fallbacks** — assim um erro transitório não congela o dia.

## 2. Botões de resync (invalidação manual)

Dois botões separados, dois endpoints. Cada um invalida só sua fatia.

- **"Sincronizar Garmin"** → limpa cache.db (dados Garmin). NÃO toca em ai_insights. Próximo load re-puxa Garmin.
- **"Regenerar análise"** → deleta as linhas de `ai_insights` do dia/página atual. Próximo load recomputa LLM com `force=True`.

### Endpoints novos (api/main.py)

```
POST /api/sync/garmin    → limpa cache Garmin, retorna build_* fresco
POST /api/sync/insights  → body: { page: 'hoje' | 'trends', period? }
                           deleta ai_insights correspondentes a hoje, rebuild com force=True
```

`POST /api/sync/insights` mapeia página → kind/key:
- `hoje` → delete `daily:<today>`, rebuild `build_today(force=True)`.
- `trends` → delete `trend:<period>:<today>`, rebuild `build_trends(force=True)`.

`build_today` / `build_trends` em `services.py` ganham `force=False`, repassado a `InsightEngine`.

### Frontend

Dois botões no header de Hoje e Tendências (Tendências só tem "Regenerar análise"; "Sincronizar Garmin" faz sentido em Hoje e Treinos). Spinner enquanto roda. Pós-sucesso, recarrega os dados da página.

## 3. Prompt caching

Reestrutura `ask_coach`: `system` de string única → lista de blocos. Perfil (estático em TODA chamada) marcado com `cache_control`; contexto (muda por chamada) sem cache.

```python
system = [
    {
        "type": "text",
        "text": f"Você é um coach... \n\nPERFIL DO ATLETA:\n{json.dumps(profile, ...)}\n\nResponda em português. Seja direto e prático.",
        "cache_control": {"type": "ephemeral"},
    },
    {
        "type": "text",
        "text": f"CONTEXTO ATUAL:\n{json.dumps(context, ...)}",
    },
]
```

Ganho real só em rajada (TTL do cache ~5 min): `scripts/backfill.py` e páginas com múltiplos detail-views próximos. Custo zero adicionar — perfil é prefixo idêntico em toda chamada. Com o output cache matando as chamadas diárias, este item beneficia principalmente o backfill.

## 4. Testes

- `HistoryDB.ai_insights`: get/set/delete, miss retorna None, set sobrescreve (PK).
- `InsightEngine` com `db` mockado/real: 2 lookups consecutivos → `ask_coach` chamado **1×** (cache funciona).
- `force=True` → re-chama `ask_coach` e sobrescreve linha.
- Fallback **não** é cacheado.
- `activity_insight` ignora data (mesma id sempre hit após primeiro).
- `ask_coach` monta lista de blocos com `cache_control` no primeiro (perfil), sem no segundo (contexto). Mockar cliente Anthropic, inspecionar `system` passado.
- Endpoints `/api/sync/garmin` e `/api/sync/insights` em `tests/test_api.py`.

## Não-objetivos (YAGNI)

- Sem hash de input — escolhido per-day + botão manual.
- Sem invalidação automática intradiária — botão "Regenerar análise" cobre.
- Sem cache de planos — já persistidos em `weekly_plan`.
- Sem prompt caching do contexto — só do perfil.
