# Limitações — Eleições 2026 (por fase)

## Fase 1 — Validação matemática

- Sem BU/RDV não é possível ir além da coerência interna; nenhuma identidade acima prova o conteúdo das urnas.
- `detalhe_votacao_secao` e `votacao_secao` foram gerados em 26/10; os demais em 28/10. Como todas as somas cruzadas fecham,
  não há evidência de retotalização entre as datas, mas a comparação é entre fotografias distintas.
- Nulos técnicos e seções agregadas não existem no grão de seção; análises por seção devem usar `QT_VOTOS_NULOS`.
- O fator 2 do Senador é regra constitucional de 2026 (constante `SENATE_SEATS_RENEWED_2026`), verificada pelos dados.
- Os testes `tests/test_hypotheses.py::test_update_status_*` assumem H01 em `proposed`; passam a falhar após a marcação
  `computed` exigida pelo brief (não editados por pertencerem a outro agente).

## Fase 2 — Descritivo

- Nenhum valor aqui é teste de hipótese; `p_empirico` em `turnout_mun` é percentil descritivo, sem FDR. Classe de todos os achados: descritivo/estatístico.
- Extremos municipais estão enviesados para municípios pequenos (variância); coluna `QT_APTOS` acompanha.
- Totais do placar devem ser conferidos contra `val_agregacao_niveis` (Fase 1).

## Fase 3 — Demografia

- Crosswalk externo (2018, sem licença declarada) exigiu correção por nome em 7 códigos; recomendável substituir por correspondência oficial TSE quando disponível.
- Boa Esperança do Norte/MT sem `pop_16mais`; 1 município sem razão.

## Fase 4 — Virada 1º→2º turno — declaração de falácia ecológica

Todas as "transferências" são estimativas AGREGADAS a partir de totais por unidade. Elas não observam nem permitem inferir o voto de qualquer eleitor individual. Frases do tipo "eleitores de X votaram em Y" NÃO são sustentadas por estes resultados; o que existe são (i) intervalos determinísticos compatíveis com os totais e (ii) coeficientes de um modelo que assume homogeneidade entre unidades (Goodman), cuja violação é conhecida. Os IC bootstrap medem incerteza amostral do modelo, não a indeterminação do problema.

## Fase 4 — Virada 1º→2º turno

- Inferência ecológica (acima). Goodman assume coeficientes iguais entre municípios; heterogeneidade por UF em swing_eco_regressao mostra que isso não vale.
- Bounds puros são quase vazios de informação para finalistas grandes; só a hipótese de retenção (não verificável) os estreita.
- Resíduos studentizados escalam com √N: cidades grandes aparecem com studentizado alto apesar de resíduo de ~1 pp; usar `residuo_pp` como effect size e o estrato por porte como referência.
- p_empirico é percentil dentro do estrato (uniforme por construção); os flags vêm de p_param (z robusto). Nada aqui é forense: "anomalia estatística; requer auditoria de BU".

## Fase 5 — Anomalias e matriz de risco

- Sem `perfil_eleitor_secao`, não há controle socioeconômico: extremos de comparecimento/nulos refletem escolaridade, ruralidade e presídios.
- Seções agregadas não são identificáveis no nível de seção; usou-se `QT_SECOES_AGREGADAS` da zona como flag (grosseira). Não há voto em trânsito neste pacote.
- Regex de local especial é heurística (40% de recall nas unânimes); escolas em terras indígenas sem o termo no nome não são marcadas.
- Modelo nulo da unanimidade (binomial) e p do último dígito são anticonservadores; q pequenos nesses testes não devem ser lidos como raridade real.
- O ranking de seções flagadas como `secao_gemea` não tem peso no score (sem componente em STRATEGY); aparece em finding_types e severity.

## Nota adicional — review

- Reprodução baseada nas tabelas já calculadas + recontagem do placar Presidente.
- Sem download de BU/hash; classe forense vazia por definição.
