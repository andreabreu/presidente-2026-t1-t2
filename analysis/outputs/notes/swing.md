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
