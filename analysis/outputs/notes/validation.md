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
