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
