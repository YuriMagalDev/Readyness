# BRIEF CRIATIVO — Design da "Hoje" (liberdade dirigida)

> Use este arquivo com uma ferramenta de design/geração de UI (Claude Design, frontend-design,
> v0, etc.). Diferente do `02-DESIGN.md` (que é prescritivo), aqui você tem **liberdade
> criativa**. Não copie o layout antigo. Proponha uma direção visual nova e distinta — só
> respeite o que o app PRECISA comunicar.

## Contexto do produto (entenda antes de criar)

App pessoal de coaching de corrida + hipertrofia, desktop, 1 usuário (atleta intermediário,
Garmin Forerunner 55). Tela principal = "Hoje": responde "posso treinar hoje e em que
intensidade?" e mostra o estado do corpo com dados do relógio + 1 LLM local.

A alma do app é **confiança**: o usuário não confia em número órfão nem em conselho sem
fundamento. Então o design existe pra transmitir credibilidade, não só estética.

## O que o design DEVE comunicar (inegociável)

1. **Veredito do dia** — um estado claro (ex: pode treinar / pegue leve / descanse) com a
   razão. É decidido por regra, é confiável; trate-o como o herói da tela.
2. **Frescor por métrica** — cada número carrega "de quando é" e um estado: fresco /
   desatualizado / ausente / estimado. O usuário precisa sentir, batendo o olho, no que dá
   pra confiar e no que está faltando. Isso é central — não é detalhe.
3. **Insights rastreáveis** — observações curtas da IA, cada uma ancorada nas métricas que a
   geraram (a fonte aparece junto). Conclusão sem fonte não existe.
4. **Poucas métricas-chave em destaque** — não despejar tudo. O resto vive em outra tela.

## Realidades dos dados (desenhe pra elas, não pro caso ideal)

- Muitas métricas vêm **vazias** com frequência (o FR55 não mede tudo; sem sincronizar, quase
  tudo é "ausente"). O design tem que ficar **bom mesmo com metade dos dados faltando** — o
  vazio não pode parecer bug nem poluir.
- Valores têm naturezas diferentes: escalares (FC, passos), tempo (predição de prova em mm:ss),
  índices (Body Battery 0-100, stress), texto curto (insights).
- Há entrada manual (auto-avaliação 1-5) — opcional no fluxo, pode entrar com elegância ou
  ficar fora da Hoje (sua escolha de design).

## Liberdade (faça diferente)

- **Layout, hierarquia, ritmo visual:** livre. Não precisa ser "semáforo à esquerda + cards à
  direita". Surpreenda — pode ser um hero central, um painel de "prontidão" tipo cockpit, uma
  timeline do dia, cartões com peso visual proporcional à relevância, o que servir à mensagem.
- **Estética:** livre (claro/escuro, tipografia, cor, densidade). Fuja do dashboard genérico
  de admin. Pode ter personalidade (atleta, performance, calma matinal — você decide o tom).
- **Como representar frescor:** livre — badge, opacidade, "há 3 dias", anel, o que comunicar
  melhor "confiança/idade do dado" sem virar ruído.
- **Como mostrar a rastreabilidade:** livre — chips, hover que revela fontes, expandir, linha
  conectando conclusão→números. Só precisa ficar claro que cada insight tem origem.

## Anti-objetivos (o que já falhou)

- ❌ Despejar ~30 métricas numa grade na tela inicial → poluição (rejeitado).
- ❌ Mostrar "pouco demais" a ponto de parecer vazio/sem valor (também rejeitado).
- ❌ Número sem contexto de frescor.
- ❌ Visual genérico de template administrativo.
- O equilíbrio certo: **denso em sinal, limpo em ruído.**

## Restrições técnicas (leves)

- Desktop, tela larga (use o espaço horizontal).
- Vai virar React/TypeScript (componentizável), mas o brief é conceitual — entregue a
  **direção visual** (layout + componentes + estados), não precisa de código de produção.
- Precisa de estados de: carregando, dado fresco, dado ausente/estimado, análise indisponível
  (LLM local fora do ar → veredito ainda aparece, insights vazios).

## Entregável

1-3 conceitos visuais distintos da tela "Hoje" (mockup/protótipo), mostrando explicitamente:
o veredito-herói, 3-5 métricas-chave com seus estados de frescor, e a lista de insights com
fontes — incluindo como cada um se comporta quando o dado está faltando. Aponte sua
recomendação e o porquê.

## Dado de exemplo pra preencher o mockup

```json
{
  "veredito": { "status": "amarelo", "motivo": "FC repouso 5 bpm acima da média e dívida de sono 2.4h", "recomendacao": "Treino leve hoje; durma cedo." },
  "chave": [
    { "label": "FC repouso", "valor": "58 bpm", "delta": "+5 vs média 7d", "frescor": "fresco" },
    { "label": "Body Battery", "valor": "30", "frescor": "fresco" },
    { "label": "Dívida de sono", "valor": "2.4 h", "frescor": "fresco" },
    { "label": "VO2max", "valor": "48", "frescor": "estimado · há 6 dias" },
    { "label": "Peso", "valor": "—", "frescor": "ausente" }
  ],
  "insights": [
    { "texto": "FC repouso elevada + bateria baixa indicam recuperação incompleta.",
      "fontes": [ {"label":"FC repouso","valor":"58 bpm"}, {"label":"Body Battery","valor":"30"} ] },
    { "texto": "Predições de prova ainda sem dado — falta um treino cronometrado.",
      "fontes": [ {"label":"Prova 5k","valor":"—","frescor":"estimado"} ] }
  ]
}
```
