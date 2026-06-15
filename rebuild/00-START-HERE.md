# Reconstrução — GarminAI Coach (LLM local)

Este pacote resume o **núcleo** de um app de coaching de saúde/treino que integra Garmin
Connect com uma LLM **local** (sem provedor pago). Use estes prompts pra reconstruir do zero
num agente de código, na ordem abaixo.

## O que você tem aqui

1. **01-CORE.md** — o que o app É: conceito, arquitetura, modelo de dados, as 3 camadas,
   princípios que fazem ele bom. Dê isto ao agente como contexto-base.
2. **02-DESIGN.md** — guia de UI/UX da tela principal ("Hoje"): layout limpo, frescor por
   métrica, insights rastreáveis. Dê isto ao agente que faz o frontend.
3. **03-LOCAL-LLM.md** — como plugar uma LLM local (Ollama/llama.cpp) no lugar da API paga,
   com roteamento de modelo e contrato de saída JSON.
4. **04-CLAUDE-DESIGN-BRIEF.md** — brief CRIATIVO pra ferramenta de design. Dá contexto +
   liberdade pra propor uma direção visual NOVA (não o layout antigo). Use este em vez do
   `02` quando quiser que o design surpreenda; use o `02` quando quiser o layout já validado.

## Como usar (fluxo sugerido)

1. Abra um agente de código numa pasta nova.
2. Cole **01-CORE.md** + **03-LOCAL-LLM.md** e peça: "faça o brainstorming e um spec da
   camada de dados+confiança, depois a de análise rastreável. Stack: Python/FastAPI +
   SQLite + LLM local. Sem provedor pago."
3. Implemente camada por camada (dados → análise → UI). Cada camada com testes (TDD) e
   commits frequentes.
4. Na UI, use **02-DESIGN.md** como guia.

## Princípio que não pode se perder

> **Confiança no dado e na análise.** Toda métrica mostra "de quando é" (frescor). Toda
> conclusão da IA cita os números que a geraram (e some se não tiver fonte real). O veredito
> "treinar hoje?" é **determinístico por regra**, não opinião da LLM.

## Stack alvo

- Python 3.11+, FastAPI + uvicorn (1 usuário, desktop, IO-bound — performance não é gargalo).
- SQLite local (cache + histórico).
- Frontend React/TypeScript (Vite), servido pelo próprio FastAPI em produção.
- `garminconnect` (SSO) pra dados; LLM local pra texto (ver 03).
