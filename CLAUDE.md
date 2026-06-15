# CLAUDE.md — Readiness (coach pessoal Garmin)

## O que é
Painel **pessoal** (1 usuário: Yuri) de coaching de corrida + hipertrofia, rodando no
**desktop**. Puxa dados do Garmin Connect (Forerunner 55), centraliza num catálogo de
métricas com frescor, e gera uma análise diária com uma **LLM local** (sem provedor pago).
Responde todo dia: "posso treinar hoje e em que intensidade?".

Sem login, sem cadastro, sem multiusuário, sem marketing. Abre direto no painel do dia.

> **Contexto completo da reformulação está em `rebuild/`** — leia antes de mudanças grandes:
> `01-CORE.md` (núcleo), `02-DESIGN.md` (UI validada), `03-LOCAL-LLM.md` (LLM local),
> `04-CLAUDE-DESIGN-BRIEF.md` (brief criativo de UI).

## Princípio que guia tudo: CONFIANÇA
1. **Frescor por métrica** — todo número mostra "de quando é" (fresco / velho / ausente /
   estimado). Visível, parte da identidade, não rótulo escondido.
2. **Análise rastreável** — todo insight da LLM cita as métricas que o geraram; insight sem
   fonte real é **descartado**.
3. **Veredito por regra** — o semáforo "treinar hoje?" é **determinístico** (regras sobre FC,
   bateria, sono), nunca opinião da LLM. Treino do dia não depende da LLM estar de pé.

## Stack
- Python 3.11+, FastAPI + uvicorn (1 usuário, IO-bound → performance da linguagem não é
  gargalo; o gargalo é rede Garmin + inferência local).
- SQLite local (cache + histórico).
- `garminconnect` (SSO) pra dados.
- **LLM local** via Ollama (`http://localhost:11434`) — ver `rebuild/03-LOCAL-LLM.md`.
- Frontend React/TypeScript (Vite), servido pelo FastAPI em produção.

## Arquitetura em 3 camadas (construir de baixo pra cima)
1. **Dados + Confiança** — catálogo curado (~20 métricas) em código; tabela longa
   `metric_value(date, metric_key, value, measured_at, source)`; coletores puros por domínio;
   frescor calculado na leitura; check-ins manuais 1-5 (hidratação/energia/soreness/comida).
2. **Análise rastreável** — veredito determinístico (regra) + insights da LLM com citações
   validadas (descarta key inventada / insight sem fonte). Cache por dia.
3. **UI "Hoje"** — limpa: veredito-herói + 3-5 métricas-chave (com frescor) + insights com
   chips de fonte. NÃO despejar a grade completa aqui (vai numa aba "Métricas").

## LLM local (regra obrigatória)
- Toda geração de texto passa por `src/llm.py` (cliente Ollama). Nada de API paga, nada de
  `anthropic`/`cache_control`.
- Roteamento por env: `LLM_MODEL_QUICK` (análise diária, 90%) vs `LLM_MODEL_DEEP` (planos).
- Saída JSON (`format:"json"` no Ollama) + parse tolerante + fallback (insights=[]).
- Modelo local alucina mais → manter a validação de citações sempre.

## Perfil do atleta (`athlete_profile.json`)
Arquivo local obrigatório, incluído como contexto em todo prompt. Campos nulos: **perguntar
ao usuário, nunca inventar**. Nunca enviar à API do Garmin.

## Regras pro Claude Code
1. **Cache primeiro** — nunca rechamar Garmin (TTL ~6h) nem a LLM se já tem dado fresco do dia.
2. **Frescor sempre visível** por métrica.
3. **Insight sem fonte = descartado.** Veredito = regra, não LLM.
4. **Campos nulos do perfil** → perguntar antes de gerar planos.
5. **Sem dado sensível em log** (mascarar email/senha).
6. **Forerunner 55**: sem HRV contínuo confiável, sem SpO2 contínuo, sem training status
   estável — essas métricas costumam vir ausentes; o app tem que ficar bom com metade vazia.
7. **TDD por camada, commits pequenos.** Migração sem quebrar tela antiga = dual-write.
8. **Frontend robusto**: mapas de config sempre com fallback (status desconhecido → neutro,
   nunca tela preta). Tipos TS derivados do JSON real da API (contrato front↔back tem que bater).

## Variáveis de ambiente (.env)
```
GARMIN_EMAIL=...
GARMIN_PASSWORD=...
CACHE_TTL_HOURS=6
LLM_BASE_URL=http://localhost:11434
LLM_MODEL_QUICK=qwen2.5:7b
LLM_MODEL_DEEP=llama3.1:8b
```

## Estrutura
```
src/
  metric_catalog.py · metric_status.py · metric_reader.py
  collectors/         # normalizadores puros por domínio
  garmin_client.py    # wrappers cacheados + retry rate-limit
  history_db.py · ingestor.py
  daily_analysis.py   # veredito (regra) + insights (LLM local + validação)
  llm.py              # cliente Ollama
api/  services.py · main.py
web/  React/Vite (tela Hoje + aba Métricas)
rebuild/  prompts-fonte da reformulação (01..04)
```

## Deploy desktop (Windows)
`iniciar.bat` na raiz: entra na pasta, builda o front se faltar, sobe
`uvicorn api.main:app --port 8000 --reload`, abre o navegador. Ollama precisa estar rodando.
Parar: Ctrl+C. Trocou build → hard-refresh (Ctrl+Shift+R) no navegador.
