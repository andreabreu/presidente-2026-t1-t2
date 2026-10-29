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
