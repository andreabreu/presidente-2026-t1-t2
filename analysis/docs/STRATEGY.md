# STRATEGY.md — Estratégia de pesquisa (Agente 7)

Escopo: dados abertos TSE 2026 (`ESTRUTURA.md`). Princípio-mestre: **anomalia ≠ fraude**. Nenhum número entra no HTML sem `source_id` de tabela gerada por script e sem tentativa de refutação (Agente 8).

---

## 1. Plano priorizado (valor/custo, decrescente)

Convenções: unidade = granularidade da linha; controles = variáveis de estratificação do modelo nulo; `output` = nome da tabela em `outputs/tables/` (vira `source_id`); "parar quando" = critério de encerramento.

### P1 — Fase 1 · Validação matemática (custo baixo, valor máximo: tudo depende disso)

| # | Item | Dados | Unidade | Controles | output | Parar quando |
|---|------|-------|---------|-----------|--------|--------------|
| 1.1 | Identidades de balanço (aptos = comparecimento + abstenções; comparecimento = válidos + brancos + nulos; nominais + legenda = válidos) | `detalhe_votacao_munzona`, `detalhe_votacao_secao` | mun/zona e seção, por turno/cargo | — | `val_balanco_munzona`, `val_balanco_secao` | 100% das linhas testadas; resíduo listado com magnitude abs/rel |
| 1.2 | Consistência de agregação Σseção = zona = município = UF = BR | `votacao_secao_*`, `votacao_candidato_munzona`, `detalhe_*` | candidato × nível | — | `val_agregacao_niveis` | Todas as hierarquias fechadas ou divergência documentada |
| 1.3 | Divergência entre fontes (candidato vs detalhe vs seção; BR vs BRASIL para Presidente) | os três pacotes | mun/zona × turno | — | `val_divergencia_fontes` | Tabela zerada ou cada diferença explicada (voto em trânsito, anulados sub judice) |
| 1.4 | Limites físicos: votos < 0, comparecimento > aptos, % fora de [0,100], seção com 0 aptos e votos > 0 | `detalhe_secao`, `votacao_secao` | seção | — | `val_limites_fisicos` | Lista fechada |

### P2 — Fase 2 · Descritivo (custo baixo, valor alto: contexto para tudo)

| # | Item | Dados | Unidade | Controles | output | Parar quando |
|---|------|-------|---------|-----------|--------|--------------|
| 2.1 | Placar Presidente 1º/2º, margem, por UF e município | `votacao_candidato_munzona_BR` | UF, município | — | `desc_placar_presidente` | Totais batem com `val_agregacao_niveis` |
| 2.2 | Comparecimento / abstenção / brancos / nulos: distribuição, por UF, top/bottom 50 municípios | `detalhe_munzona` | município × turno | porte (faixa de aptos), região | `desc_participacao_uf`, `desc_participacao_mun` | Painel pronto com quantis por estrato |
| 2.3 | Governador: placar e 2º turno onde houve | `votacao_candidato_munzona_{UF}` | UF, município | — | `desc_placar_governador` | Todas as UFs com 2º turno identificadas pelos dados |
| 2.4 | Deputado Federal: totais por partido/candidato, HHI e nº efetivo de candidatos | `votacao_candidato_munzona_BRASIL`, `votacao_partido_munzona` | UF; mun para SP/MG/RJ | — | `desc_depfed_partido`, `desc_concentracao` | Nacional + SP/MG/RJ concluídos |

### P3 — Fase 4 · Virada 1º→2º (custo médio, valor alto: tema central do brief)

| # | Item | Dados | Unidade | Controles | output | Parar quando |
|---|------|-------|---------|-----------|--------|--------------|
| 4.1 | Saldos agregados: votos finalistas 1º vs 2º, delta abs/%, pool residual (eliminados + brancos/nulos + abstenção) | `votacao_candidato_munzona_BR`, `detalhe_munzona` | município, zona | — | `swing_saldos_mun`, `swing_saldos_zona` | Identidade "ganho A + ganho B = pool − novos nulos/brancos − Δabstenção" verificada |
| 4.2 | Bounds de transferência (mín/máx) por município — método determinístico, sem suposições | idem | município | — | `swing_bounds_mun` | Intervalos calculados para 100% dos municípios |
| 4.3 | Regressão ecológica (Goodman) com erros-padrão robustos; baseline proporcional como comparador | idem | município (pesos = aptos) | UF, porte, Δcomparecimento | `swing_eco_regressao` | Coeficientes em [0,1] com IC; se fora, reportar como limitação, não truncar silenciosamente |
| 4.4 | Resíduos anômalos da virada: desvio do padrão estadual após controles, FDR | 4.3 + `detalhe` | município, zona; seção (BR) | UF, porte, Δcomparecimento | `swing_residuos_flag` | q_fdr calculado; top-50 listado com effect size |

### P4 — Fase 5 · Anomalias e scores (custo médio; só após P1–P3)

| # | Item | Dados | Unidade | Controles | output | Parar quando |
|---|------|-------|---------|-----------|--------|--------------|
| 5.1 | Comparecimento extremo (percentil empírico dentro de UF × porte) | `detalhe_secao`, `detalhe_munzona` | seção, município | UF, porte, tipo de local (quando disponível) | `anom_comparecimento` | p_empirico + q_fdr |
| 5.2 | Seções ~100% para um candidato com N alto (N ≥ limiar em `config.yaml`) | `votacao_secao_BR` | seção | UF, porte | `anom_secao_unanime` | Lista com N, candidato, local |
| 5.3 | Correlação nulos/brancos × margem, por UF (Spearman, com IC bootstrap) | `votacao_secao`, `detalhe_secao` | seção dentro de UF | UF, porte | `anom_nulos_margem` | Effect size + IC por UF |
| 5.4 | Seções "gêmeas" (vetor de votos idêntico/quase idêntico em seções distintas, N alto) | `votacao_secao_BR` | par de seções | mesmo município excluído? → documentar escolha | `anom_secoes_gemeas` | Comparar com taxa esperada por simulação |
| 5.5 | `risk_score` consolidado (§3) | todas as `anom_*` + `val_*` | seção, município | — | `anom_risk_score` | Ranking + sensibilidade ±20% nos limiares (`anom_sensibilidade`) |
| 5.6 | Modelo de urna (`CD_MODELO_URNA`) vs métricas — **só descritivo** | `detalhe_secao` | seção | UF, porte | `desc_modelo_urna` | Tabela pronta; sem teste de hipótese |

### P5 — Fase 3 · Demografia (custo alto: depende de download externo; valor médio)

| # | Item | Dados | Unidade | Controles | output | Parar quando |
|---|------|-------|---------|-----------|--------|--------------|
| 3.1 | Aptos / população total e / pop ≥16 (IBGE Censo 2022 por faixa etária; documentar interpolação) | `detalhe_munzona` + IBGE SIDRA | município | região, porte | `demo_aptos_pop` | Join por código IBGE ≥ 99% dos municípios |
| 3.2 | Flags: aptos/pop≥16 > 1,0 ou < quantil 1% dentro de porte | 3.1 | município | porte, região | `demo_flags` | Lista + explicação conhecida (eleitores de municípios vizinhos, fronteira, cidades-dormitório) |

Ordem recomendada de execução: P1 → P2 → P3 → P4 → P5. Demografia só entra no `risk_score` se o join fechar; caso contrário vai para "Limitações".

### Fases 6 e 7 (transversais)
- Fase 6 (HTML): cada tabela acima é um `source_id`; sumário executivo só lê `rev_vereditos`.
- Fase 7 (Revisor): `rev_vereditos` com colunas `achado_id, classe, veredito, motivo`. Só SUSTENTADO/FRÁGIL entram no executivo.

---

## 2. NÃO FAZER

| Não fazer | Justificativa |
|-----------|---------------|
| Benford 1º dígito em totais municipais/zona | Totais agregados dependem do tamanho da unidade; Benford falha sob H0 em dados eleitorais (literatura: Deckert, Myagkov & Ordeshook 2011). Gera falsos positivos e desinformação. |
| Benford 2º dígito ou last-digit como evidência isolada | Só como triagem exploratória, nunca em `risk_score`; se usado, apenas em seções com N ≥ 100 e com simulação do nulo. |
| Afirmar transferência de voto individual ("eleitores de X votaram em Y") | Falácia ecológica; só intervalos agregados (bounds + regressão ecológica) com ressalva explícita. |
| Usar "probabilidade de fraude", "chance de manipulação" ou similares | Nenhum modelo aqui estima fraude; estima raridade sob referência empírica. |
| Rotular achado como forense sem BU/hash/log | Não há fonte independente baixada (ESTRUTURA.md §7). Máximo possível hoje: documental ou estatístico. |
| Carregar `BRASIL` inteiro em RAM ou misturar `BR` com `BRASIL` | Dupla contagem de Presidente; custo computacional desnecessário. |
| Varredura de seções sem FDR e sem taxa esperada de falsos positivos | ~500 mil seções × vários testes → milhares de "anomalias" espúrias ao nível 5%. |
| Nomear candidatos hardcoded no código | Descobrir via `consulta_cand` + votos (brief). |
| Comparar com 2022 antes de fechar P1–P4 | Valor marginal; só se sobrar tempo (backlog §5). |
| Clustering espacial (Moran I) sem shapefile/vizinhança | Sem matriz de vizinhança não há teste; backlog. |
| Interpretar `CD_MODELO_URNA` causalmente | Alocação de modelos não é aleatória (correlaciona com UF/porte); só descritivo. |
| Testar hipóteses geradas por LLM sem registro prévio em `hypotheses.yaml` | Evita p-hacking e HARKing. |

---

## 3. Vocabulário de scores (obrigatório no HTML e nas tabelas)

| Termo | Definição | Faixa |
|-------|-----------|-------|
| `p_empirico` | Percentil da métrica da unidade dentro da distribuição de referência do mesmo estrato (UF × faixa de porte; para seção também tipo de local quando houver). `p_empirico = 0,999` significa "mais extremo que 99,9% das unidades comparáveis". Não é p-valor paramétrico. | [0,1] |
| `q_fdr` | q-valor Benjamini–Hochberg do teste correspondente, calculado dentro de cada bateria (um conjunto de testes = uma correção). Reportar junto o número esperado de falsos positivos: `n_testes × q`. | [0,1] |
| `effect_size` | Magnitude padronizada (diferença em pontos percentuais, razão, ou z-MAD) — sempre acompanha `q_fdr`. | real |
| `risk_score` | Combinação ponderada de componentes normalizados em [0,1]; pesos em `config.yaml`. Serve para **ordenar prioridade de auditoria**, não para medir fraude. | [0,1] |

Pesos sugeridos iniciais (somam 1; revisar na análise de sensibilidade):

| Componente | Peso | Fonte |
|------------|------|-------|
| Divergência documental entre fontes (binário ou magnitude relativa) | 0,30 | `val_divergencia_fontes`, `val_limites_fisicos` |
| Resíduo de virada extremo (1 − q_fdr, se q < 0,10; senão 0) | 0,25 | `swing_residuos_flag` |
| Comparecimento extremo (idem) | 0,15 | `anom_comparecimento` |
| Seção ~unânime com N alto | 0,15 | `anom_secao_unanime` |
| Nulos/brancos × margem fora do padrão da UF | 0,10 | `anom_nulos_margem` |
| Demografia impossível (aptos/pop≥16 > 1) | 0,05 | `demo_flags` (0 se join não fechar; renormalizar) |

Frase obrigatória junto a qualquer `risk_score`: **"O risk_score ordena unidades para eventual auditoria documental; não é probabilidade de fraude nem de erro."**

Classes de achado (coluna `classe` em toda tabela de flags):

| Classe | Critério | Exemplo |
|--------|----------|---------|
| `documental` | Violação de identidade aritmética ou divergência entre arquivos oficiais do mesmo evento | Σseções ≠ zona; comparecimento > aptos |
| `estatistico` | H0 rejeitada após controles e FDR, sem prova documental | Virada residual com q < 0,05 |
| `forense` | Prova em fonte independente (BU, hash, log) divergente do resultado | **Não atingível com os dados atuais** — manter coluna vazia e dizer isso |

---

## 4. Glossário para o sumário executivo

Regra: toda frase descreve o dado e o que seria preciso para ir além. Nunca "fraude", "manipulação", "suspeito". Preferir "inconsistência", "fora do padrão", "requer verificação de boletim de urna".

| Resultado técnico | Tradução leiga (modelo de frase) |
|-------------------|----------------------------------|
| Identidade de balanço violada em N linhas | "Em N de M registros, a soma de votos não bate com o comparecimento informado (diferença total de X votos, Y% do total). Isso indica inconsistência de arquivo e pede conferência com o boletim de urna." |
| Divergência entre fontes | "Dois arquivos oficiais do TSE informam totais diferentes para a mesma unidade (X vs Y). A causa pode ser critério de publicação (ex.: votos em trânsito); não dá para concluir mais sem o boletim." |
| `p_empirico` alto | "Esta [seção/município] teve [métrica] mais extrema que 99,x% das unidades comparáveis do mesmo estado e porte." |
| `q_fdr` baixo | "Ao testar N unidades, esperamos cerca de K resultados extremos por acaso; encontramos J. Os J − K excedentes merecem olhar mais atento, mas qualquer um deles individualmente ainda pode ser acaso." |
| `risk_score` | "Nota de prioridade de 0 a 1 para ordenar onde conferir primeiro. Não mede chance de fraude." |
| Bounds de transferência | "Pelos totais, entre X% e Y% dos votos do candidato eliminado podem ter ido para A. É um intervalo sobre grupos de eleitores, não sobre pessoas." |
| Regressão ecológica | "Nos municípios onde o candidato C teve mais votos no 1º turno, o candidato A cresceu em média Z p.p. no 2º. Isso descreve municípios, não eleitores individuais." |
| Resíduo de virada extremo | "Neste município a mudança entre turnos ficou fora do padrão do estado, mesmo considerando porte e comparecimento. Fica como item a verificar, não como conclusão." |
| Seção ~100% para um candidato | "N seções registraram quase todos os votos para um único candidato. Isso ocorre naturalmente em localidades pequenas e homogêneas; listamos as de maior tamanho para conferência." |
| Correlação nulos × margem | "Nos estados X, seções com mais nulos tenderam a ter margem [maior/menor]. A associação é fraca/moderada e tem várias explicações possíveis (perfil do eleitorado, voto de protesto)." |
| aptos/pop≥16 > 1 | "Há mais eleitores aptos do que população adulta estimada. Causas comuns: eleitores que moram em outro município, estimativas populacionais defasadas. Não indica irregularidade por si." |
| Achado REFUTADO pelo Revisor | "Um resultado preliminar de [tema] não se sustentou quando reproduzido independentemente; foi retirado do sumário e está na aba Refutações." |
| Classe `forense` vazia | "Nenhuma afirmação de irregularidade material é possível com os arquivos atuais: faltam boletins de urna, logs e hashes." |

---

## 5. Backlog "próximos passos" (ordem de valor)

1. **Boletins de Urna (BU) das top-200 seções por `risk_score`** — único caminho para a classe `forense`; cruzar BU × `votacao_secao`. Dataset "Boletins de Urna 2026" no portal; baixar só UFs/zonas necessárias.
2. **Hashes/assinaturas dos arquivos de resultado e dos BUs** — verificar integridade do que já foi baixado; registrar em `run_manifest.json`.
3. **IBGE Censo 2022 — população por faixa etária municipal (SIDRA tabela 9514 ou equivalente)** — desbloqueia P5 com pop ≥16 direta, sem interpolação.
4. **Resultados 2022 (mesmos pacotes, mesma granularidade)** — baseline histórico por seção/município para comparecimento e nulos; melhora o modelo nulo de 5.1 e 5.3.
5. **Logs de urna (Gedai) das seções top-50** — horários de abertura/encerramento, reinicializações; só descritivo até haver método validado.
6. **Malha municipal IBGE (shapefile/GeoJSON 2022)** — mapa coroplético e matriz de vizinhança para Moran I (bootstrap espacial da virada).
7. **Cadastro de locais de votação com geolocalização (TSE "Eleitorado e locais")** — estratificar seção por tipo de local (urbano/rural, escola/outro).
8. **Export JSON das anomalias** (`outputs/anomalies_export.json`) para auditoria externa — baixo custo, fazer logo após 5.5.

---

## 6. Decisão de escopo inicial

**Recomendação:**
- **Presidente** em UF → município → zona para **todas** as fases (P1–P5) usando `votacao_candidato_munzona_BR` + `detalhe_munzona` (arquivos pequenos, cobertura nacional, 1º e 2º turnos no mesmo pacote).
- **Seção** nacional apenas para Presidente (`votacao_secao_2026_BR`, ~242 MB), necessário para 5.2, 5.4 e resíduos de virada em grão fino.
- **Outros cargos (Governador, Deputado Federal)** em mun/zona nacionalmente; **seção** só em **SP, MG, RJ** (`votacao_secao_2026_{SP,MG,RJ}`, ~1,4 GB dos 2,9 GB totais; ~40% do eleitorado).

**Justificativa:** o tema central do brief (virada 1º→2º) existe só para Presidente e governadores com 2º turno; Presidente é o único cargo com arquivo nacional por seção único e comparável. SP/MG/RJ concentram o maior eleitorado e os maiores arquivos, dando poder estatístico para proporcionais sem processar 27 UFs. Expandir para as demais UFs por seção só se P4 indicar resíduos concentrados fora desses estados (critério objetivo: ≥ 20% das flags de `swing_residuos_flag` em nível município numa UF fora do trio).
