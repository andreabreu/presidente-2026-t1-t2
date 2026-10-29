# Métodos — Eleições 2026 (concatenação das notas por fase)

## Fase 1 — Validação matemática

# Validação matemática (Fase 1) — `python -m tse.validation`

Hipóteses cobertas: H01–H10, H24, H27, H29, H30. Tabelas: `val_resumo` (uma linha por check), `val_inconsistencias`
(toda violação de identidade exata, linha a linha), `val_balanco_secao`, `val_balanco_munzona`, `val_legenda_partido`,
`val_limites_fisicos`, `val_agregacao_niveis`, `val_divergencia_fontes`, `val_br_vs_brasil`, `val_cobertura_cand`,
`val_timestamps`, `val_timestamps_geracao`, `val_totalizacao_datas`, `val_tamanho_secao`. Escopos: Presidente lido de `BR`;
demais cargos de `<UF>` (seção) e `BRASIL` (mun/zona). 92 checks, todos os turnos e cargos (3.029.823 linhas de seção,
37.521 linhas mun/zona, 69,9 mi linhas de votacao_secao). Códigos descobertos: branco = 95, nulo = 96; voto de legenda em
votacao_secao = `SQ_CANDIDATO = -3` com `NR_VOTAVEL` = número do partido.

## Identidades que valem em 100% das linhas (`val_resumo`, n_violations = 0)

Seção (`detalhe_votacao_secao`, BS03): `QT_COMPARECIMENTO × v = QT_VOTOS_NOMINAIS + QT_VOTOS_LEGENDA + QT_VOTOS_BRANCOS +
QT_VOTOS_NULOS + QT_VOTOS_ANULADOS_APU_SEP`, com v = 2 para Senador (renovação de 2/3 em 2026: dois votos por eleitor) e
v = 1 nos demais cargos. `QT_VOTOS_ANULADOS_APU_SEP` é zero em todas as linhas. A forma com v = 1 (BS02, hipótese H02 como
redigida) falha exatamente nas 497.897 linhas de Senador e em nenhuma outra.

Mun/zona (`detalhe_votacao_munzona`): BM02 `APTOS = COMPARECIMENTO + ABSTENCOES + QT_ELEITORES_SECOES_NAO_INSTALADAS`;
BM04 `COMPARECIMENTO × v = QT_VOTOS`; BM05 `QT_VOTOS = TOTAL_VALIDOS + BRANCOS + TOTAL_NULOS + TOTAL_ANULADOS +
TOTAL_ANUL_SUBJUD + ANULADOS_APU_SEP`; BM06 `CONCORRENTES = TOTAL_VALIDOS + TOTAL_ANULADOS + TOTAL_ANUL_SUBJUD`;
BM07 `TOTAL_NULOS = NULOS + NULOS_TECNICOS`; BM08 `TOTAL_VALIDOS = NOMINAIS_VALIDOS + TOTAL_LEG_VALIDOS`;
BM09 `TOTAL_LEG_VALIDOS = LEG_VALIDOS + NOM_CONVR_LEG_VALIDOS`; BM10/BM11 totais de anulados e sub judice = nominais +
legenda; BM13 `TOTAL_SECOES = SECOES_PRINCIPAIS + SECOES_AGREGADAS` (não instaladas já estão em principais).
A identidade de H03 como redigida (BM03, sem anulados/sub judice) falha em 15.732 linhas (41,9%), nas quais há votos
anulados ou sub judice; BM05 é a forma correta.

Agregação (H05, `val_agregacao_niveis`): Σ seção = mun/zona em zona, município, UF e Brasil para APTOS, COMPARECIMENTO,
ABSTENCOES, BRANCOS, `QT_VOTOS_NULOS` (não `QT_TOTAL_VOTOS_NULOS`: nulos técnicos não aparecem por seção), nº de seções
= `QT_SECOES_PRINCIPAIS` (não `QT_TOTAL_SECOES`: o arquivo de seção não lista seções agregadas) e
`NOMINAIS + LEGENDA = CONCORRENTES + NULOS_TECNICOS`.

Fontes (H06/H07/H09/H10, `val_divergencia_fontes`, `val_legenda_partido`): Σ votacao_secao por classe = detalhe_secao
(brancos, nulos, nominais, legenda, total) em 100% das 3.029.823 seções; Σ candidato `QT_VOTOS_NOMINAIS_VALIDOS` por
zona = detalhe (DF02) e por partido = partido_munzona (LP02); Σ partido = detalhe (DF05, DF06); LP01 interna do partido.
BR = BRASIL (H08) linha a linha em candidato_munzona, detalhe_munzona e detalhe_secao; UF = BRASIL em detalhe_secao.
Cadastro (H29): todo SQ_CANDIDATO com votos (19.234 em mun/zona; 19.504 em seção) existe em consulta_cand com mesmos
NR_CANDIDATO, SG_PARTIDO e DS_SIT_TOT_TURNO. Limites (H04/H27/H30): sem negativos, comparecimento ≤ aptos em 100%,
82 seções não instaladas com comparecimento 0 e sem linhas em votacao_secao, nenhuma seção anulada, nenhuma com aptos 0.
Carimbos (H24): um único DT/HH_GERACAO por dataset; última totalização (máx. 25/10/2026 23:21:51), recebimento de BU e
primeira totalização parcial sempre anteriores à geração do arquivo.

## Inconsistências encontradas (`val_inconsistencias`, 26.491 linhas) e explicações testáveis

1. BS01 (H01) `APTOS = COMPARECIMENTO + ABSTENCOES` falha em 82 linhas (0,0027%), todas em `SG_UF = ZZ` (exterior),
   41 seções × 2 turnos, 423 aptos, `ST_SECAO_INSTALADA = Não`, `DS_ORIGEM_VOTO = Totalização`: aptos > 0 com comparecimento
   e abstenções iguais a 0. Em mun/zona o mesmo resíduo é exatamente `QT_ELEITORES_SECOES_NAO_INSTALADAS` (BM02 = 100%).
   Hipótese: eleitores de seções não instaladas não são contados como abstenção. Classe documental, magnitude 846 eleitores.
2. DF01 (H06) Σ votacao_secao por candidato ≠ candidato_munzona em 14.672 pares zona×candidato (0,22%), 628.629 votos,
   250 candidatos (p.ex. 274.411 votos de um candidato a Governador no RJ). Em 100% dos casos o candidato NÃO existe em
   votacao_candidato_munzona (lado esperado = 0) e consta em consulta_cand como `NÃO ELEITO`; para candidatos presentes
   nos dois arquivos não há divergência alguma. Hipótese confirmada por DF08 (0 violações): `QT_VOTOS_NULOS_TECNICOS` por
   zona = votos desses candidatos "órfãos" + votos de legenda a partidos sem linha em votacao_partido_munzona na UF/cargo
   (PCO/SP 1.173, PRD/SE 309, Avante/PB 304, Solidariedade/SE 126). Ou seja, candidaturas indeferidas/retiradas após a
   urna foram excluídas do arquivo por candidato e seus votos convertidos em nulos técnicos. Requer confirmação processual.
3. DF03 (H07, candidata) Σ candidato `QT_VOTOS_NOMINAIS` ≠ válidos + anulados + sub judice em 85 zonas (MS, Dep. Estadual),
   16.884 votos = exatamente os votos com `NM_TIPO_DESTINACAO_VOTOS = 'Válido (legenda)'` (88 linhas); excluindo esse
   destino a identidade fecha (DF04 = 100%). Esses votos entram em `QT_VOTOS_LEG_VALIDOS` do detalhe, não em
   `QT_VOTOS_NOM_CONVR_LEG_VALIDOS` (que é zero em todo o arquivo).
4. AG NOMINAIS/LEGENDA (candidatas) divergem em 663 zonas = 85 do item 3 + 578 do item 2 (legenda para partido sem
   candidatos contada como legenda na seção e como nulo técnico na zona). Soma nominais + legenda fecha em 100%.
5. CC06 (informativa): 1.223 candidatos de consulta_cand sem linha de votos (965 `#NULO`, 258 `NÃO ELEITO`);
   `DS_SITUACAO_CANDIDATURA` é `#NE` em todo o cadastro, impossibilitando filtrar deferidos.

## Limitações
- Sem BU/RDV não é possível ir além da coerência interna; nenhuma identidade acima prova o conteúdo das urnas.
- `detalhe_votacao_secao` e `votacao_secao` foram gerados em 26/10; os demais em 28/10. Como todas as somas cruzadas fecham,
  não há evidência de retotalização entre as datas, mas a comparação é entre fotografias distintas.
- Nulos técnicos e seções agregadas não existem no grão de seção; análises por seção devem usar `QT_VOTOS_NULOS`.
- O fator 2 do Senador é regra constitucional de 2026 (constante `SENATE_SEATS_RENEWED_2026`), verificada pelos dados.
- Os testes `tests/test_hypotheses.py::test_update_status_*` assumem H01 em `proposed`; passam a falhar após a marcação
  `computed` exigida pelo brief (não editados por pertencerem a outro agente).

## Fase 2 — Descritivo

# Fase 2 — Descritivo (features + turnout)

Scripts: `python -m tse.features` (placar, concentração), `python -m tse.turnout` (participação, seções, modelo de urna). Logs em `logs/features.log` e `logs/turnout.log`. Todas as tabelas têm `.csv`, `.parquet` e `.meta.json` em `outputs/tables/`.

## O que foi calculado
- Presidente (scope=BR, `QT_VOTOS_NOMINAIS_VALIDOS`, partido via `consulta_cand` scope=BR): `desc_placar_presidente` (nacional), `desc_placar_presidente_uf`, `desc_placar_presidente_mun`, `desc_vencedor_presidente_uf`, `desc_vencedor_presidente_mun` (1º/2º colocados, margem em votos e p.p., HHI, nº efetivo), `desc_mudanca_rank_presidente_mun` (posição 1º→2º turno).
- Governador (scope=BRASIL, CD_CARGO=3): `desc_placar_governador_uf`, `desc_governador_uf`.
- Deputado Federal (scope=BRASIL, CD_CARGO=6): `desc_depfed_partido` (nominais + legenda, nacional e por UF), `desc_depfed_top` (top 30 nacional; top 20 em SP, RJ, MG). Cadeiras não calculadas.
- Participação Presidente (detalhe_votacao_munzona scope=BR): `turnout_uf`, `turnout_mun` (com z-MAD e percentil empírico por UF × quintil de aptos), `turnout_zona`, `turnout_distribuicao`, `turnout_outliers` (top/bottom 30, aptos ≥ 1.000), `turnout_transito`; Deputado Federal 1º turno: `turnout_depfed_uf`.
- Seções (detalhe_votacao_secao scope=BR): `desc_secao_tamanho` (H30), `desc_modelo_urna` (H26).
- Figuras (plotly JSON): `fig_presidente_vencedor_uf`, `fig_turnout_hist_taxa_{comparecimento,nulos_comp,brancos_comp}`.

## Principais números
- Placar nacional (`desc_placar_presidente`): 1º turno — Flavio Bolsonaro (PL) 56.104.503 (47,03% dos válidos), Lula (PT) 53.879.538 (45,16%), Augusto Cury (Avante) 2,89%, Renan Santos (Missão) 2,24%, Ronaldo Caiado (PSD) 2,18%; 12 candidatos com votos. 2º turno — Lula 64.256.232 (51,79%) × Flavio Bolsonaro 59.826.041 (48,21%); margem 4.430.191 votos (3,57 p.p.). Inversão de posição entre turnos.
- Por UF no 2º turno (`desc_vencedor_presidente_uf`): menor margem MG (0,87 p.p., Lula), depois TO (2,74, Bolsonaro), AP (5,76), RJ (6,20), SP (7,69). Maiores: PI (51,8 p.p., Lula), RR (44,9, Bolsonaro), BA (42,6).
- Municípios vencidos (`desc_vencedor_presidente_mun`, sem ZZ): 1º turno 2.908 Bolsonaro / 2.663 Lula; 2º turno 2.875 Lula / 2.696 Bolsonaro.
- Governador (`desc_governador_uf`): 6 UFs com 2º turno (AC, AM, DF, ES, RN, TO); menor margem no 2º turno RN (1,54 p.p.). 1º turno decidido em 21 UFs; mais apertados PR (50,11%) e RJ (50,88%).
- Deputado Federal (`desc_depfed_partido`, nível BRASIL): PL 22,7% dos válidos, PT 13,0%, PSD 8,3%, Republicanos 7,0%, MDB 6,9%, União 6,9%, PP 6,7%. Voto de legenda = 3,43 milhões (3,0% dos válidos); PT com maior fração de legenda (6,8%). Mais votados (`desc_depfed_top`): Nikolas Ferreira 3.119.318, Lucas Pavanato 3.038.438, Erika Hilton 1.596.472.
- Participação (`turnout_uf`, sem exterior): 1º turno aptos 157.828.968, comparecimento 79,16%, brancos 1,84% e nulos 2,94% do comparecimento; 2º turno comparecimento 81,01%, brancos 1,12%, nulos 2,13%. Exterior (ZZ): 916.534 aptos, comparecimento 37,3%. Com ZZ: 78,92% e 80,78%.
- Distribuição municipal (`turnout_distribuicao`, 5.571 municípios): comparecimento 1º turno mediana 79,4% (p1 68,0%, p99 87,7%); nulos/comp mediana 2,77% (p99 5,87%); brancos/comp mediana 1,51%.
- Extremos (`turnout_outliers`, aptos ≥ 1.000): maior comparecimento Bela Vista do Piauí/PI 92,7% (3.462 aptos); menores concentrados no Vale do Jequitinhonha/MG (Rio Vermelho 59,9%); maior nulos/comp Queimada Nova/PI 8,0%.
- Voto em trânsito (`turnout_transito`): nenhuma linha com ST_VOTO_EM_TRANSITO = 'S' em detalhe_votacao_munzona (BR e BRASIL); não há componente separável neste pacote.
- Seções (`desc_secao_tamanho`): 0 seções com aptos = 0, 0 com comparecimento > aptos, 0 com aptos = 0 e votos; mediana de aptos por seção entre 271 (PI) e 361 (AM); mínimo 20, máximo 534 nas UFs; ZZ mediana 770, máx 930.
- Modelo de urna (`desc_modelo_urna`): UE 2020 (200 mil seções) e UE 2022 (199 mil) dominam; UE 2015 88 mil; UE 2013 12 mil. Nulos/comparecimento quase idênticos entre modelos (2,72%–2,95% no 1º turno). Comparecimento do UE 2013 (71,6%) é puxado pelo exterior (ZZ usa UE 2013 e UE 2015, com 37%–40% de comparecimento); excluindo ZZ, 78,8%–79,4% em todos os modelos.

## Hipóteses geradas (registrar antes de testar)
- Municípios de baixo comparecimento concentram-se em microrregião específica de MG (Jequitinhonha); testar efeito regional vs porte.
- Brancos/nulos por UF variam 2× (RO 1,3% a AL 4,4% nulos); candidatos a controle em `anom_nulos_margem`.
- H26: diferença de comparecimento entre modelos desaparece ao excluir ZZ; o teste formal deve estratificar por UF × faixa de aptos.

## Limitações
- Nenhum valor aqui é teste de hipótese; `p_empirico` em `turnout_mun` é percentil descritivo, sem FDR. Classe de todos os achados: descritivo/estatístico.
- Extremos municipais estão enviesados para municípios pequenos (variância); coluna `QT_APTOS` acompanha.
- Totais do placar devem ser conferidos contra `val_agregacao_niveis` (Fase 1).

## Fase 3 — Demografia

# Fase 3 — Demografia (aptos × população IBGE)

Script: `python -m tse.demography.metrics` (join em `src/tse/demography/join.py`; download IBGE não alterado). Log em `logs/demography.log`. Tabelas: `demo_join_cobertura`, `demo_aptos_pop`, `demo_aptos_pop_uf`, `demo_outliers`; figura `fig_demo_aptos_vs_pop16` (log-log, flags rotulados).

## Dados e join
- Numerador: `detalhe_votacao_munzona` scope=BR, 1º turno, CD_CARGO=1, aptos/comparecimento somados sobre zonas por município; exterior (ZZ) excluído → 5.571 municípios.
- Denominadores: `pop_total` (estimativa IBGE 2026) e `pop_16mais` (Censo 2022, soma exata de idades 16+).
- Cobertura (`demo_join_cobertura`): 5.571/5.571 municípios (100%), 100% dos aptos. 5.563 por código TSE→IBGE; 7 corrigidos pelo nome porque o crosswalk de 2018 traz códigos deslocados (Lagoa Real, Laje, Lajedão, Lajedinho, Lajedo do Tabocal — BA; Santiago do Sul ↔ Santa Terezinha do Progresso — SC); 1 por fallback de nome (Boa Esperança do Norte/MT, criado em 2025, sem `pop_16mais`). 13 divergências de grafia/renomeação mantidas (ex.: Boa Saúde/RN = Januário Cicco; São Thomé das Letras).
- Estratos: UF × porte, porte = quintis nacionais de `pop_total` com cortes em [0,25; 0,5; 0,75; 0,9] (config `demography.porte_quantiles`); estratos com n < 10 ficam sem z-MAD (AP, RR, AC, DF em parte).

## Principais números (`demo_aptos_pop`, `demo_aptos_pop_uf`)
- Agregado nacional: aptos/pop_total = 0,737; aptos/pop_16mais = 0,986.
- Mediana municipal aptos/pop_16mais = 1,080 (p5 0,89; p95 1,45); aptos/pop_total mediana 0,819.
- Flag aptos > pop_16mais: 3.986 de 5.571 municípios (71,5%). Fração por porte: 98% nos menores (P1), 79% (P2), 68% (P3), 53% (P4), 23% nos maiores (P5). Comparecimento > pop_16mais: 1.023 municípios.
- Top 10 aptos/pop_16mais: Davinópolis/GO 2,71 (4.145 aptos; 1.530 pop 16+); Itaubal/AP 2,48; Anhangüera/GO 2,28; Chapada de Areia/TO 2,25; Cutias/AP 2,16; Tibau/RN 2,14; Novo Santo Antônio/PI 2,10; Pilar de Goiás/GO 2,08; Bodó/RN 2,06; Oliveira de Fátima/TO 2,03.
- Por UF: razão agregada aptos/pop_16mais entre 0,914 (RR) e 1,105 (AP); acima de 1 em 16 UFs (AM, DF, CE, SE, BA, RN, PE, AL, AC, MA, TO, PA, RO, PB, PI, AP).
- `demo_outliers` (|z_mad| > 3,5 dentro de UF × porte): 119 municípios em aptos/pop_16mais, 92 em aptos/pop_total, 92 em comparecimento/pop_16mais. Maiores desvios: Lavínia/SP (0,44; z −8,5 — presença de penitenciárias infla a população residente), Davinópolis/GO (z +7,4), Tibau/RN (+7,3), Balbinos/SP (0,39; z −7,3), Ouvidor/GO (+7,1), Águas de São Pedro/SP (+6,8).

## Leitura e caveats
- A regra "aptos > pop_16mais" (H20) não discrimina: é a norma em municípios pequenos. Causas conhecidas: domicílio eleitoral distinto da residência (cidades-dormitório, municípios polo, segunda residência), crescimento 2022→2026 do denominador defasado, inscrições de 16–17 anos (facultativas) e títulos não cancelados. Nenhum valor indica irregularidade por si; classe `estatistico`.
- Recomendação para `risk_score`: usar `aptos_pop_16mais_z_mad` (desvio dentro de UF × porte), não a flag bruta; peso 0,05 conforme STRATEGY §3.
- Sem p-valor nem FDR: `p_empirico` é percentil descritivo. Não há teste de hipótese formal nesta etapa.

## Hipóteses geradas
- Razão alta correlaciona negativamente com porte (ver tabela por porte); modelar log(aptos) ~ log(pop_16mais) + UF e usar resíduos como métrica alternativa.
- Municípios com razão baixa (< 0,6) coincidem com unidades prisionais ou grandes instituições (Lavínia, Balbinos, Pacaembu/SP) — verificável com cadastro de locais de votação.

## Limitações
- Crosswalk externo (2018, sem licença declarada) exigiu correção por nome em 7 códigos; recomendável substituir por correspondência oficial TSE quando disponível.
- Boa Esperança do Norte/MT sem `pop_16mais`; 1 município sem razão.

## Fase 4 — Virada 1º→2º turno

# swing — Virada 1º→2º turno (Fase 4, P3; H15–H19)

Script: `python -m tse.swing` (flags `--sem-secao`, `--sem-governador`, `--so-governador`, `--bootstrap N`). Seed `config.seed` = 20261028; log em `logs/swing.log`.
Escopo: Presidente (`scope=BR`, CD_CARGO=1) em município, zona e seção; Governador (CD_CARGO=3) nas UFs com 2º turno detectadas nos dados (AC, AM, DF, ES, RN, TO), em município/zona.
Finalistas detectados nos dados: A = NR 13 (mais votado no 2º turno), B = NR 22. Eliminados "principais" (≥1% dos válidos): 70, 14, 55; demais agrupados em `outros_eliminados_t1`. Brancos/nulos identificados por `NM_VOTAVEL` (95/96).

## DECLARAÇÃO DE FALÁCIA ECOLÓGICA (vale para todas as tabelas `swing_*`)
Todas as "transferências" são estimativas AGREGADAS a partir de totais por unidade. Elas não observam nem permitem inferir o voto de qualquer eleitor individual. Frases do tipo "eleitores de X votaram em Y" NÃO são sustentadas por estes resultados; o que existe são (i) intervalos determinísticos compatíveis com os totais e (ii) coeficientes de um modelo que assume homogeneidade entre unidades (Goodman), cuja violação é conhecida. Os IC bootstrap medem incerteza amostral do modelo, não a indeterminação do problema.

## A) Saldos (swing_saldos_mun / _zona / _secao; swing_aptos_estabilidade)
- Unidade = (UF, município[, zona[, seção]]); votos T1 de `votacao_candidato_munzona` (mun/zona) ou `votacao_secao` (seção), totais de `detalhe_votacao_*`. Nulos em mun/zona = `QT_TOTAL_VOTOS_NULOS` (inclui técnicos); em seção o votável 28 (5.246 votos, nulos técnicos no mun/zona) aparece como candidato eliminado — diferença documentada.
- `pool_residual` = eliminados + Δ(brancos+nulos) + Δcomparecimento; identidade ganho A + ganho B = pool satisfeita em 100% dos municípios e zonas (`identidade_ok`). Nacional (swing_saldos_mun): A 53.879.538→64.256.232 (+10.376.694), B 56.104.503→59.826.041 (+3.721.538); pool 14.098.232 = 9.316.747 eliminados + 1.821.246 brancos/nulos a menos + 2.960.239 de comparecimento a mais. 89 municípios com queda de A, 950 com queda de B, 75 com queda de ambos (H16: quedas devem ser lidas junto com `delta_comp`).
- H15 (swing_aptos_estabilidade): 499.248 seções presentes nos dois turnos, 0 só em um turno; 55.722 (11,2%) com `QT_APTOS` diferente (|Δ| máx 772; soma |Δ| 74.692; total de aptos BR idêntico nos dois turnos). Maior fração em DF (29,2%), ZZ, SE, RN. Consequência metodológica: N de referência = max(aptos T1, aptos T2) por unidade.
- H19 (colunas `z_mad_delta_comp`, `q_fdr_delta_comp` em swing_saldos_secao): z robusto de Δtaxa de comparecimento dentro de UF×porte; 2.207 seções com q<0,05 (falsos positivos esperados ≈ 110); extremos: Inácio Martins/PR z.34 s.133 (−70,7 pp), Mangaratiba/RJ z.54 s.140 (−54,2 pp). CSV traz top-1000 por |z|; parquet completo.

## B) Transferência agregada (swing_bounds_mun, swing_bounds_uf, swing_eco_regressao, swing_baseline_comparacao, swing_fluxo_matriz)
- Bounds Duncan–Davis por unidade: low = max(0, R_r + C_d − N), high = min(R_r, C_d); agregação = Σlow/ΣR_r, Σhigh/ΣR_r. Calculados por seção, por município e diretamente nos totais de UF (`agregado_de`). Variante `duncan_davis_retencao_total` (hipótese: eleitores de finalistas repetem o voto) é comparador, não evidência; 4.793/5.757 municípios compatíveis com ela.
- H18: para destinos finalistas, bounds de seção ⊆ município ⊆ UF em 100% das células; 19/928 violações (≤1,1 pp) ocorrem só em células `abstencao_t2`, por N de referência diferir entre níveis quando aptos mudam (H15). Bounds puros são largos (ex.: 13→13 em [0,08; 1,00] via município, [0,10; 1,00] via seção); informativos apenas para o que é impossível (ex.: B→B ≤ 0,998 agregado, ou seja, retenção total de B é incompatível com os totais).
- Regressão ecológica (Goodman) com unidades = municípios, pesos = comparecimento T2, sem intercepto: `goodman_simplex` (coeficientes em [0,1] e soma por origem = 1, SLSQP sobre matrizes de Gram) e `goodman_wls` (irrestrito, diagnóstico). IC 95% por bootstrap de 400 reamostragens de municípios. Ajuste nacional e por UF (heterogeneidade; UFs com <10 municípios omitidas: DF).
- Fluxo nacional (simplex; [IC]): 13→13 1,00 [1,00; 1,00]; 22→22 1,00 [0,998; 1,00]; 70→13 0,53 [0,48; 0,61], 70→brancos/nulos 0,47 [0,39; 0,52], 70→22 0,00 [0; 0]; 14→22 0,68 [0,63; 0,73], 14→13 0,33 [0,23; 0,37]; 55→22 0,55 [0,52; 0,58], 55→13 0,38 [0,35; 0,41], 55→brancos/nulos 0,08; brancos/nulos T1→13 0,85 [0,81; 0,91]; abstenção T1→13 0,05 [0,04; 0,06], →22 0,00; outros→22 1,00 [0,91; 1,00]. WLS irrestrito produz coeficientes fora de [0,1] (ex.: 14→abstenção −0,65; brancos/nulos→13 0,98) — sinal de má especificação; reportado, não truncado.
- 6/32 células nacionais do simplex ficam fora dos bounds Duncan–Davis agregados por município (todas células de retenção/abstenção dos finalistas, por ≤0,002), indicando que o modelo força retenção total que os totais não permitem em todos os municípios.
- Baseline proporcional (finalistas retêm 100%; resto se divide na proporção T1): share nacional de A entre válidos 0,4899 (T1 dupla) → 0,5179 observado (+2,97 pp; 3,68 M votos acima do baseline). Por UF o excesso varia de +1,5 pp (BA) a +3,6 pp (GO).

## C) Resíduos anômalos (swing_residuos_flag / _resumo / _sensibilidade / _modelo)
- Modelo: WLS de share_a_t2_valid ~ shares T1 (A, 70, 14, 55, outros, brancos+nulos; B omitido) + log aptos + taxa comp T1 + Δcomp pp + EF porte + EF UF; pesos = comp T2. Seção: todas as variáveis centradas por município (EF município absorve UF). Resíduo studentizado interno → z robusto (mediana/MAD) dentro de UF×porte (estrato <30 → porte nacional) → p bilateral normal → q BH por nível. effect_size = resíduo em pp. R² ponderado: 0,9997 (mun), 0,9996 (zona), 0,93 (seção, within).
- Flags q<0,05 (falsos positivos esperados = n_flag×q): município 37/5.715 (1,9); zona 43/6.250 (2,2); seção 69/499.205 (3,5).
- Top municípios flagados (resíduo pp / studentizado): Salvador/BA +1,09 / 18,2 (porte >200k; efeito pequeno em pp, enorme em N); Belo Monte/AL −10,9 / −8,2; Santo Antônio de Lisboa/PI −8,5 / −6,7; Tóquio/ZZ −4,8; Crateús/CE −2,5; Nagóia/ZZ −4,1; Caldeirão Grande/BA −5,3; Rafael Godeiro/RN +8,6; Lauro de Freitas/BA +1,2; Hamamatsu/ZZ −4,4. Seções: Manoel Urbano/AC z.3 s.160 −35 pp; Barcelos/AM z.18 s.37 +31 pp; Feijó/AC z.7 s.67 +38 pp; bloco de seções da zona 2 de São Paulo −12 a −13 pp.
- Sensibilidade (Jaccard vs base): sem controles 0,51 (mun) / 0,47 (zona) / 0,74 (seção); q×0,8: 0,81 / 0,70 / 0,81; q×1,2: 0,97 / 0,98 / 0,88. Conjunto de flags é moderadamente sensível aos controles — tratar como triagem.
- Governador (swing_governador_*): fluxos simplex por UF com IC largos (n pequeno); DF usa zonas (1 município). Flags q<0,05: AC 1, AM 4, DF 2 (zona), ES 5, RN 0, TO 3 (município) e 5 (zona).

## Hipóteses testáveis geradas
1. Seções flagadas em C com Δcomparecimento extremo (H19) coincidem? Cruzar `swing_residuos_flag` × `flag_delta_comp`.
2. Bloco de seções da zona 2/SP com resíduo −12 pp: mesmo local de votação (`nr_local_votacao`)? Se sim, hipótese de troca de seção/local entre turnos.
3. Municípios do exterior (ZZ) concentram resíduos negativos: estimar modelo separado para ZZ.
4. 75 municípios em que ambos os finalistas perdem votos: explicados integralmente por `delta_comp`? (H16 por município com IC.)

## Limitações
- Inferência ecológica (acima). Goodman assume coeficientes iguais entre municípios; heterogeneidade por UF em swing_eco_regressao mostra que isso não vale.
- Bounds puros são quase vazios de informação para finalistas grandes; só a hipótese de retenção (não verificável) os estreita.
- Resíduos studentizados escalam com √N: cidades grandes aparecem com studentizado alto apesar de resíduo de ~1 pp; usar `residuo_pp` como effect size e o estrato por porte como referência.
- p_empirico é percentil dentro do estrato (uniforme por construção); os flags vêm de p_param (z robusto). Nada aqui é forense: "anomalia estatística; requer auditoria de BU".

## Fase 5 — Anomalias e matriz de risco

# Fase 5 — Anomalias estatísticas e matriz de risco (Agentes 2+4+5)

Script: `python -m tse.anomalies` (código em `src/tse/anomalies/`, log em `logs/anomalies.log`). Escopo: Presidente (scope=BR) por seção, turnos 1 e 2 (998.496 seções×turno; 498.950 testáveis por turno após excluir aptos < 50, não instaladas e comparecimento 0); Deputado Federal 1º turno por seção em SP, MG, RJ (193.393 seções) só para unanimidade, último dígito e gêmeas. Grupo de referência: UF × faixa de aptos (50–199, 200–299, 300–399, 400+) × turno. Hipóteses H11, H12, H13, H23, H25, H28 marcadas `computed`.

**O risk_score ordena unidades para eventual auditoria documental; não é probabilidade de fraude nem de erro.** Nenhuma linha recebe classe `forense`: os arquivos atuais só permitem anomalia estatística ou inconsistência documental.

## O que foi calculado (source_id)
- `anom_comparecimento` (H11) e `anom_brancos_nulos` (H12): z robusto (MAD), percentil empírico bilateral e q BH por turno. O BH usa `p_valor_z` (normal sobre o z MAD): o percentil empírico tem mínimo 2/n por estrato e, com ~500 mil testes, nunca alcança q < 0,05 — decisão metodológica documentada no meta.
- `anom_secao_unanime` e `anom_unanime_municipio` (H23): seções com share do mais votado ≥ 0,98 e ≥ 100 votos nominais; excesso municipal contra binomial com prevalência do líder municipal (p de Poisson, BH por turno).
- `anom_nulos_margem` e `anom_nulos_margem_uf` (H13): OLS da margem do líder sobre taxa de nulos, efeitos fixos de UF e quintil de aptos, HC1; robustez por seção centrada no município (erros agrupados); Spearman por UF.
- `anom_ultimo_digito` (H28): qui-quadrado de uniformidade por UF × turno × candidato, limiares 10 e 100 votos. Sem Benford de 1º dígito.
- `anom_secoes_gemeas` e `anom_gemeas_municipio` (H25): pares com vetor completo idêntico (incl. brancos/nulos) e comparecimento ≥ 100; nulo por permutação (200 perms Presidente, 20 Dep. Federal; seed do config).
- `anom_fingerprint_uf` + `outputs/figures/anom_fingerprint_t{1,2}.json`: descritivo Klimek (comparecimento × share do vencedor nacional), sem teste.
- `anom_risk_score`, `anom_top200_secoes`, `anom_mun_ranking`, `anom_resumo`, `anom_sensibilidade`, `anom_export.json`.
- Hooks: `val_inconsistencias` e `swing_residuos_flag` ausentes no momento da execução → componentes `divergencia_fontes` (0,30) e `residuo_virada` (0,25) zerados e pesos renormalizados sobre comparecimento (0,15), unanimidade (0,15) e nulos/brancos (0,10); demografia (0,05) idem. Basta reexecutar após essas tabelas existirem (chaves CD_MUNICIPIO, NR_ZONA, NR_SECAO, NR_TURNO e coluna q_fdr).

## Principais números
- `anom_resumo`: comparecimento extremo q < 0,05 em 1.164 seções (T1) e 2.034 (T2) de 498.950 — 0,2–0,4%, muito abaixo dos 24.947 falsos positivos nominais a 5%; 98% das flags são de comparecimento baixo (cauda inferior) e 60% carregam flag de exclusão (presídio, zona com seções agregadas, local especial). Brancos+nulos extremos: 1.074 (T1) e 898 (T2), todos na cauda alta, 73% com flag de exclusão.
- Unanimidade (`anom_secao_unanime`): 534 seções (160 T1, 374 T2); 527 com o candidato 13 e 7 com o 22. Concentram-se no Alto Solimões/Rio Negro (AM: São Paulo de Olivença, Tabatinga, Amaturá, Santo Antônio do Içá, São Gabriel da Cachoeira, Barcelos), Uiramutã/RR, Parauapebas/PA, Pesqueira/PE. 40% dos nomes de local contêm INDÍGENA/ALDEIA (regex em config.yaml); muitos outros são escolas em terras indígenas sem o termo no nome (ex.: E. E. D. PEDRO I em Santo Antônio do Içá, Escola Estadual Urubá em Pesqueira — território Xukuru). 259 de 12.919 municípios×turno com q < 0,05 em `anom_unanime_municipio`; o modelo binomial é anticonservador (ignora heterogeneidade intramunicipal), então esse número superestima o excesso. Nenhuma seção quase unânime em Deputado Federal SP/MG/RJ.
- Nulos × margem (`anom_nulos_margem`): município, T1: coeficiente −1,53 (IC95 −2,16 a −0,90; HC1), R² parcial 0,5%, n = 5.706 — municípios com mais nulos têm margem do líder ligeiramente menor; T2: −0,59 (IC −1,57 a 0,40), não distinguível de zero. Seção dentro de município: T1 −0,15 (IC −0,33 a 0,03), T2 −0,34 (IC −0,53 a −0,14), R² < 0,1%. Associação fraca e sem controle socioeconômico; não causal.
- Gêmeas (`anom_gemeas_municipio`): T1 Presidente 0 pares idênticos observados (nulo médio 0,09); T2 966 pares (vetor de 4 votáveis) contra 789,5 esperados por permutação, nenhum município com q < 0,05 — compatível com coincidência em vetores curtos. Dep. Federal SP/MG/RJ: 0 pares. Nada sugere duplicação de exportação.
- Último dígito (`anom_ultimo_digito`): com limiar 10, 81 de 136 grupos Presidente T1 e 480 de 601 Dep. Federal têm q < 0,05 com dígito 0 dominante (desvio mediano 0,14) — artefato de contagens pequenas em distribuição decrescente, não de digitação. Com limiar 100, 26/56 (T1) e 24/56 (T2) ainda têm q < 0,05, mas o desvio máximo mediano é 0,01 (ex.: Lula SP T1, n = 38.932, maior desvio 0,012): efeito ínfimo detectado por n enorme. A contagem é eletrônica; o teste não entra no risk_score.
- Fingerprint (`anom_fingerprint_uf`): coeficiente de bimodalidade do comparecimento ≤ 0,55 em todas as UFs (limiar 0,555); share do vencedor até 0,78 em UFs com forte clivagem interna; fração de seções no canto (comparecimento > 0,95 e share > 0,95) ≤ 0,14%. ZZ (exterior) tem comparecimento médio 38% e é estrato próprio.
- `anom_risk_score`: 996.652 seções severity 1, 1.784 severity 2, 60 severity 3 (≥ 2 achados independentes), nenhuma ≥ 4. Top-10 por risk_score: Barcelos/AM z18 s40 T2 (0,999; comparecimento + nulos + unanimidade; E. M. Indígena Ajuricaba), Parauapebas/PA z106 s330/244/365 T1 (0,75; EMEF Indígena Bep Karoti Xikrin), Barcelos z18 s40 T1 e s38 T2, Confresa/MT z28 s200 T2 (Escola Estadual Tapiitawa), Goiatins/TO z32 s70 T2 (Escola Indígena Crokroc), Fernando Falcão/MA z97 s214 T2 (C.E.E.I. Kapertyc Canela), Ipixuna/AM z45 s63 T2 (Aldeia Piau). Todos os top-10 são escolas indígenas com flag `local_especial` e/ou `zona_com_agregadas`.
- `anom_mun_ranking` (risk_score médio): Fernando de Noronha/PE T2, Mato Grosso/PB, La Paz/ZZ, Serra do Navio/AP, Pilar de Goiás/GO — municípios pequenos onde poucas seções pesam muito.
- `anom_sensibilidade`: limiares ±20% mantêm 1.838–1.856 seções severity ≥ 2; Jaccard do top-200 contra a base 0,59 (−20%) e 0,72 (+20%) — a ordenação fina do topo é sensível aos limiares e deve ser lida como fila, não como lista fechada.

## Critério de disparo de BU (FORENSIC_CHECKLIST §5)
Existem seções com severity 3, q < 0,01 e ≥ 100 eleitores, mas todas com flag de exclusão (local especial/zona com agregadas). Sem flag, as linhas de severity 3 restantes são do tipo comparecimento + nulos em escolas comuns (ex.: Minas Novas/MG, Feijó/AC); recomenda-se revisão do Agente 8 antes de qualquer download.

## Limitações
- Sem `perfil_eleitor_secao`, não há controle socioeconômico: extremos de comparecimento/nulos refletem escolaridade, ruralidade e presídios.
- Seções agregadas não são identificáveis no nível de seção; usou-se `QT_SECOES_AGREGADAS` da zona como flag (grosseira). Não há voto em trânsito neste pacote.
- Regex de local especial é heurística (40% de recall nas unânimes); escolas em terras indígenas sem o termo no nome não são marcadas.
- Modelo nulo da unanimidade (binomial) e p do último dígito são anticonservadores; q pequenos nesses testes não devem ser lidos como raridade real.
- O ranking de seções flagadas como `secao_gemea` não tem peso no score (sem componente em STRATEGY); aparece em finding_types e severity.

## Nota adicional — closure

# Fechamento do pipeline (pós-Claude)

## Entregue agora
- `outputs/report.html` (~41 MB) — abas Executivo→Dados, tabelas filtráveis
- `outputs/tables/rev_vereditos.csv` + `rev_reproducao.csv`
- `hypotheses.yaml` — 30 hipóteses `reviewed` (14 SUSTENTADO, 13 FRÁGIL, 2 REFUTADO, 1 INCONCLUSIVO)
- Investigação: `investigation/timeline/`, `legal/limites.md`, `evidence_matrix.csv`, `sources/README.md`
- `outputs/METHODS.md`, `LIMITATIONS.md`
- Testes: **75 passed**

## Como abrir
```bash
open /Users/andreabreu/Developer/TSE/analysis/outputs/report.html
# ou
cd analysis && .venv/bin/python -m tse.report
```

## Melhorias prioritárias (próximo ciclo)
1. **Re-rodar anomalias** com hooks `val_inconsistencias` + `swing_residuos_flag` (notas dizem componentes zerados na 1ª passagem).
2. **Baixar BUs** só das top-N seções severity≥3 sem flag de exclusão (fila forense real).
3. **Baseline 2018/2022** presidente (já em `downloads/`) — mesma seção/município, delta de comparecimento e share.
4. **Enxugar report.html** (lazy-load JSON por aba; hoje embute muitas tabelas → 41 MB).
5. **Corrigir lint de dígitos** no gerador (notas verbatim / títulos com anos) ou marcar blocos `data-lint=exempt`.
6. **Crosswalk IBGE oficial** (substituir o de 2018 citado nas limitações).
7. **EI / bootstrap espacial** nas viradas (intervalos mais honestos que Goodman pontual).
8. Comparar fingerprint Klimek 2022×2026 por UF.

## Nota adicional — review

# Revisão adversarial (Agente 8)

Script: `python -m tse.review`.

## Vereditos
- SUSTENTADO: 2
- FRÁGIL: 5
- REFUTADO: 2
- INCONCLUSIVO: 1

Tabelas: `rev_vereditos`, `rev_reproducao`.
Hipóteses em `hypotheses.yaml` atualizadas para `reviewed`.

## Limitações
- Reprodução baseada nas tabelas já calculadas + recontagem do placar Presidente.
- Sem download de BU/hash; classe forense vazia por definição.
