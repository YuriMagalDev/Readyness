# DESIGN — Tela "Hoje" (UI/UX)

Guia pro agente que constrói o frontend. Uso é **desktop** (tela larga) — projetar multi-coluna,
não mobile-first. Tema escuro.

## Princípio visual

Mostrar o essencial sem poluir. A versão que despejava ~30 métricas na tela inicial foi
rejeitada por **poluição**. A tela "Hoje" deve ser limpa; a grade completa de métricas vive
numa aba separada ("Métricas"), não na Hoje.

## Layout da "Hoje" (aprovado)

```
┌────────────────────────────────────────────────────────────┐
│ Status do Dia              [🔄 Sincronizar] [💡 Regenerar]   │
├──────────────┬─────────────────────────────────────────────┤
│ VEREDITO     │ 4 cards-chave (empilhados):                  │
│ 🟢 Verde     │  ❤ FC repouso hoje vs média 7d  (delta)      │
│ (semáforo +  │  ⚡ Body Battery matinal                      │
│  recomenda-  │  🌙 Dívida de sono semanal                   │
│  ção)        │  🏃 Corridas esta semana                     │
├──────────────┴─────────────────────────────────────────────┤
│ 💡 INSIGHTS — só com o dado disponível                       │
│ • <texto do insight>                                         │
│   [FC 58bpm 🟢] [Bateria 30 🟢]   ← chips das métricas-fonte │
│ • <outro insight> [chips...]                                 │
└──────────────────────────────────────────────────────────────┘
```

- **Esquerda:** semáforo (verde/amarelo/vermelho) + motivo + recomendação. Vem do veredito
  determinístico.
- **Direita topo:** exatamente 4 cards-chave (FC, bateria, sono, corridas). Cada um com valor
  + delta curto (ex: "-5.9 bpm", "acima do limite") e cor de alerta quando ruim.
- **Embaixo:** lista de insights rastreáveis. Cada insight = 1 frase + linha de "chips" com as
  métricas que o geraram (label + valor formatado + badge de frescor). Lista vazia → "Sem
  insights hoje." discreto. NÃO inventar insight sem fonte.

## Componentes

- `FreshnessBadge(status)` → emoji + cor + tooltip "medido em …": 🟢 fresco / 🟡 velho /
  ⚪ ausente / 〰️ estimado. **Sempre com fallback** pra status desconhecido (nunca quebrar a
  tela — renderizar badge neutro em vez de crashar).
- `MetricChip(source)` → chip compacto `label valor 🟢` usado nos insights.
- `InsightList(insights)` → renderiza insights + chips.
- `Semaforo(status, motivo, recomendacao)` → também com fallback defensivo no status.
- `MetricCard(icon, label, value, delta, deltaWarn)` → os 4 cards-chave.
- `DomainGrid(metrics)` → a grade completa por domínio (prontidão/recuperação/atividade/corpo)
  com `FreshnessBadge` por célula. **Vai na aba "Métricas", não na Hoje.**

## Regras de robustez (aprendidas na marra)

1. **Nunca deixar um componente crashar a página.** Mapas de config (`CFG[status]`) sempre com
   `?? fallback`. Um status inesperado vira badge neutro, não tela preta.
2. **Contrato front↔back tem que bater exatamente.** Bug real: backend mandava
   `veredito.status` e o front lia `veredito.semaforo` → undefined → crash. Defina os tipos
   TypeScript a partir do JSON real da API e teste com o payload de verdade.
3. **Degradação graciosa:** se `/api/analysis` falhar, ainda mostra os cards e o veredito do
   `/api/today` (fallback). Só o bloco de insights fica vazio.
4. **Formatação de tempo:** predições de prova vêm em segundos → formatar `mm:ss` ([h:]mm:ss)
   na UI, com helper compartilhado.
5. **Cache de bundle:** ao trocar build, o navegador pode segurar JS velho — lembrar o usuário
   de hard-refresh (Ctrl+Shift+R) ou usar hashing de assets (Vite já faz) + recarregar.

## Botões

- "🔄 Sincronizar" → `POST /api/sync` → recarrega.
- "💡 Regenerar análise" → `POST /api/analysis` (force) → atualiza só os insights/veredito.

## Próximo passo previsto

Aba **"Métricas"** separada usando `DomainGrid`: mostra todas as métricas do catálogo
agrupadas por domínio, cada uma com frescor. Opção de esconder as ausentes pra reduzir ruído.
