# Protocolo de hipóteses, resultados e revisão — Eleições 2026

Este documento fixa como uma afirmação sai de um texto gerado por LLM e chega ao
relatório HTML. Ele é vinculante para todos os 8 agentes e para o orquestrador.

## 1. Regra zero: texto não produz número

1. Nenhum número apresentado em qualquer entregável (HTML, Markdown, resumo em
   conversa) pode ter origem em texto gerado por modelo de linguagem.
2. Todo número nasce de um script Python versionado em `analysis/src/tse/`,
   executado sobre os Parquets de `data/interim/` (ou `data/external/` para IBGE),
   e materializado em `outputs/tables/<nome>.csv` (e `.parquet`).
3. O LLM pode: propor hipóteses, escrever código, redigir prosa que **referencia**
   números por `source_id` (seção 4), interpretar resultados. O LLM não pode:
   estimar, arredondar "de cabeça", extrapolar ou citar um valor que não esteja
   em uma tabela de saída.
4. Se um texto precisa de um número que ainda não existe, o número é
   substituído pelo marcador `[[pendente:<expected_output_table>]]` até que a
   tabela seja gerada. Marcadores pendentes bloqueiam a publicação.

## 2. Ciclo de vida de uma hipótese

O registro canônico é `analysis/hypotheses.yaml`; o único caminho de escrita é
`tse.hypotheses.update_status(id, status, **campos)`, que valida o esquema e
grava de forma atômica. Edição manual do YAML após a Fase 0 é proibida.

| Status | Quem transiciona | Campos exigidos | Significado |
|---|---|---|---|
| `proposed` | Agente 6 / Agente 1 / Agente 4 | esquema base | Enunciado neutro, teste e dados definidos; sem resultado. |
| `computed` | Agente 5 | `script` (caminho em `src/tse/`), `table` (caminho em `outputs/tables/`) | Script rodou sobre os dados; tabela gerada e registrada em `run_manifest.json`. |
| `reviewed` | Agente 8 (exclusivamente) | `verdict` ∈ {SUSTENTADO, FRÁGIL, REFUTADO, INCONCLUSIVO}, `reviewed_by`, `refutation_attempts` não vazio | Revisor reproduziu e tentou refutar. |
| `published` | Orquestrador | os anteriores | Entrou no HTML na aba correspondente ao veredito. |

Regras de transição:

- Só `computed → reviewed` e `reviewed → published` são permitidas adiante;
  qualquer regressão (ex.: refazer o cálculo) volta para `computed` e apaga o
  `verdict`.
- `refutation_attempts` é uma lista de itens `{by, date, method, outcome}`
  acrescentada pelo Revisor. Um `verdict` sem pelo menos uma tentativa é
  inválido.
- Veredito `REFUTADO` ou `INCONCLUSIVO` não impede publicação: o item é
  publicado na aba **Refutações**, nunca no sumário executivo.
- O sumário executivo contém apenas `SUSTENTADO` e `FRÁGIL` (este com ressalvas
  textuais obrigatórias).

Classificação obrigatória (`class`): `documental` (inconsistência de arquivo),
`estatistico` (rejeição de H0 com controles e correção) ou `forense` (exige
prova documental externa: BU, hash, log). Nenhuma hipótese pode ser promovida de
`estatistico` para `forense` sem dados listados em `data` que ainda não existem
no repositório (ver ESTRUTURA.md §7).

## 3. Correção para múltiplas comparações e "probabilidades"

Toda hipótese `estatistico` com varredura por unidade (seção, zona, município)
declara `test.correction` (padrão: `benjamini_hochberg`, q em `config.yaml`).
Qualquer score exibido no HTML declara seu modelo no nome da coluna:
`p_empirico`, `q_fdr`, `z_mad`, `risk_score`. A expressão "probabilidade de
fraude" e seus sinônimos são proibidos em qualquer entregável.

## 4. Convenção `source_id`

Cada número no HTML é um elemento com dois atributos obrigatórios:

```html
<span data-source="outputs/tables/turnout_extremes_secao.csv"
      data-query="Q_H11_top_outliers_sp">0,9412</span>
```

- `data-source`: caminho relativo a `analysis/` da tabela CSV de origem. O
  arquivo deve existir e estar listado em `outputs/run_manifest.json` com hash.
- `data-query`: identificador da consulta que extrai o valor da tabela, no
  formato `Q_<HID>_<descricao_snake_case>`. Toda query é registrada em
  `outputs/tables/queries.yaml` com `id`, `source`, `filter`, `aggregate`,
  `value`. O gerador do HTML (`src/tse/report/`) recalcula o valor a partir da
  query no momento da renderização; um valor digitado à mão que não bata com
  a query falha a geração.
- Clique sobre o número abre a query e a linha da tabela de origem.
- Textos em prosa que mencionam quantidades usam o mesmo marcador. Um lint em
  `src/tse/report/` rejeita qualquer dígito dentro de blocos de prosa que não
  esteja envolto em `data-source`.

## 5. Abas do HTML

O relatório separa três abas com fronteiras rígidas:

1. **Hipóteses** — lista integral de `hypotheses.yaml` com `id`, `title`,
   `class`, `unit`, `null_hypothesis`, `status`. Nenhum número além de
   contagens de status. Hipóteses `proposed` aparecem aqui e em nenhum outro
   lugar.
2. **Resultados calculados** — apenas itens `computed`, `reviewed` ou
   `published` com `verdict` ∈ {SUSTENTADO, FRÁGIL} (ou ainda sem veredito,
   marcados visivelmente como "não revisado"). Toda célula numérica carrega
   `source_id`. Itens FRÁGIL exibem as ressalvas do Revisor ao lado.
3. **Refutações** — itens `REFUTADO` e `INCONCLUSIVO`, com o texto integral de
   `refutation_attempts`, o veredito e o motivo. Esta aba é tão visível quanto
   as outras; não é apêndice.

O sumário executivo (aba Executivo) é gerado exclusivamente a partir da aba
Resultados calculados filtrada por veredito.

## 6. Firewall de informação para o Revisor (Agente 8)

O Revisor opera em contexto isolado. O orquestrador monta o pacote de entrada
manualmente e nada além dele é fornecido.

**Pode receber:**

- `ESTRUTURA.md`, `docs/PROTOCOL.md`, `config.yaml`.
- Para cada hipótese a revisar: `id`, `title`, `class`, `unit`,
  `null_hypothesis`, `test`, `data`, `expected_output_table` (o enunciado
  neutro, tal como em `proposed`).
- O código do script (`script`) e a tabela de saída (`table`).
- Acesso de leitura aos Parquets de `data/interim/` e `data/external/`.
- `run_manifest.json`.

**Não pode receber:**

- Qualquer prosa interpretativa dos Agentes 1–7 (achados, "anomalia detectada",
  rankings comentados, rascunhos do sumário executivo).
- `risk_score` ou classificações de severidade já atribuídas pelo Agente 4.
- Vereditos anteriores do próprio Revisor sobre outras hipóteses, exceto os
  registrados em `refutation_attempts` do mesmo `id`.
- O HTML parcial ou qualquer figura já gerada.
- Conversa do orquestrador com outros agentes.

O Revisor devolve apenas: `verdict`, `refutation_attempts` e, quando reproduziu
o cálculo de forma independente, o caminho do script de reprodução em
`src/tse/review/`. A divergência entre a tabela original e a reprodução é em si
um resultado e vai para `outputs/tables/review_<HID>_reproduction.csv`.
