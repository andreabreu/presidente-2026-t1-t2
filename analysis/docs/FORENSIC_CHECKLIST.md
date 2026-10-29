# Checklist forense — Eleições 2026 (Agente 4: Auditoria / forense eleitoral)

Escopo: o que pode ou não ser auditado com os arquivos já baixados (`downloads/`, ver `ESTRUTURA.md`),
como classificar achados e que linguagem usar. Nenhum item deste documento afirma ou sugere fraude;
tudo aqui é especificação de verificação.

Princípio operativo: os CSVs de resultados são **derivados da totalização**. Eles permitem testar a
coerência interna da totalização e procurar anomalias estatísticas; **não** permitem verificar se a
totalização reflete o que a urna registrou. Essa segunda pergunta só é respondível com o Boletim de
Urna (BU), o RDV, o log da urna e a correspondência esperada/efetivada.

---

## 1. Matriz de auditabilidade

Legenda: **A** = auditável com arquivos atuais · **P** = parcialmente (só descritivo/estatístico) · **N** = exige fonte adicional.

| # | Item | Status | Fonte atual | O que falta / observação |
|---|------|--------|-------------|--------------------------|
| 1 | Identidades de balanço (`QT_APTOS = QT_COMPARECIMENTO + QT_ABSTENCOES`; `QT_COMPARECIMENTO = nominais + legenda + brancos + nulos`) | A | `detalhe_votacao_secao`, `detalhe_votacao_munzona` | Validar identidade exata no `leiame.pdf` (nulos técnicos, anulados sub judice entram em `QT_TOTAL_VOTOS_NULOS`). Falha = **documental**. |
| 2 | Consistência de agregação (Σ seções = zona = município = UF = BR) | A | `votacao_secao_*` × `votacao_candidato_munzona` × `detalhe_*` | Cuidado: `BR` ≠ `BRASIL`; voto em trânsito (`ST_VOTO_EM_TRANSITO`) agregado em linha própria; seções agregadas (`NR_SECAO` da seção principal) absorvem outras. Falha = **documental**. |
| 3 | Divergência entre arquivos (candidato × detalhe × seção) | A | idem | Mesmo `DT_GERACAO/HH_GERACAO`? Arquivos gerados em momentos distintos podem divergir legitimamente (totalização incremental, decisões judiciais). Registrar timestamps antes de rotular. |
| 4 | Unanimidade por seção (100% / ~100% para um votável) | P | `votacao_secao_*` | Estatístico. Falsos positivos: seções ≤50 eleitores, presídios, aldeias, hospitais, seções de trânsito. BU confirma que o número é o da urna; **não** explica a unanimidade. |
| 5 | Comparecimento extremo (≈100% ou ≈0%, ou > aptos) | P | `detalhe_votacao_secao` | > aptos = documental. ≈100% em seção pequena = esperado (binomial). Falta: `perfil_eleitor_secao` (eleitorado por seção, faixa etária) para baseline — não baixado. |
| 6 | Resíduos de virada 1º→2º turno | P | `votacao_secao_BR` (Presidente), `votacao_secao_{UF}` (Governador) | Só inferência ecológica. Seções podem mudar de local/agregação entre turnos (`NR_LOCAL_VOTACAO`, `ST_SECAO_INSTALADA`); pareamento por (UF, mun, zona, seção) exige verificação. Nunca forense. |
| 7 | Modelo de urna (`CD_MODELO_URNA`/`DS_MODELO_URNA`) vs resultado | P | `detalhe_votacao_secao` | Só descritivo. Modelo é confundido com região/porte (distribuição não aleatória). Exige regressão com controles; efeito "bruto" é inválido. Modelo real da urna usada: correspondência efetivada. |
| 8 | Timestamps `DT_ULTIMA_TOTALIZACAO` / `HH_ULTIMA_TOTALIZACAO` | P | `detalhe_votacao_munzona` | Só a nível mun/zona. Permite detectar zonas totalizadas tarde (retotalização). **Não** é o horário de encerramento da urna (isso está no BU/log). |
| 9 | `ST_SECAO_ANULADA` / `ST_SECAO_INSTALADA` | A (contagem) / N (causa) | `detalhe_votacao_secao` | Contar e localizar é auditável. O **motivo** (urna substituída, decisão judicial, não instalação) exige correspondência efetivada, log Gedai/urna e processual. |
| 10 | `QT_VOTOS_ANULADOS_APU_SEP` (apuração em separado) | A (magnitude) / N (causa) | `detalhe_votacao_munzona` | Verificar se entra ou não nas identidades de balanço. Causa (candidato sub judice, seção impugnada) exige processual e BU. |
| 11 | Voto em trânsito (`ST_VOTO_EM_TRANSITO = S`) | A (contagem) | `votacao_candidato_munzona` | Isolar antes de qualquer teste estatístico: seções de trânsito têm perfil de eleitor totalmente distinto. Confirmar como aparecem em `votacao_secao` (seção própria? `NR_SECAO` específico?). |
| 12 | Digitação / transcrição do BU na totalização | N | — | Requer BU (`bweb_*`) e/ou `arqurnatot`: comparar linha a linha `votacao_secao` × BU. É o **único** teste que converte "anomalia" em "divergência entre fontes oficiais". |
| 13 | Integridade do software da urna | N | — | Requer hashes `.sha512`, assinaturas, log Gedai e logs da urna (`logjez`). Fora do alcance de análise de resultados. |
| 14 | Urna substituída / contingência | N | — | Requer correspondência esperada vs efetivada (`CESP_*` vs `CEFT_*`). |
| 15 | RDV (Registro Digital do Voto) vs BU | N | — | Requer `arqurnatot` (`rdv`). Recontagem lógica por seção. |
| 16 | Eleitorado × população IBGE (demografia) | P | `detalhe_*` (aptos) + IBGE (externo) | Erro de alistamento vs erro de projeção IBGE indistinguíveis sem `eleitorado-2026`. |

**Resumo do não auditável hoje:** qualquer alegação sobre a urna (software, hash, horário de abertura/fechamento,
substituição, correspondência entre urna e seção, RDV × BU, BU × totalização). Com os arquivos atuais só é
possível auditar a **coerência interna da totalização** e produzir **anomalias estatísticas com controles**.

---

## 2. Padrões clássicos da literatura — aplicabilidade a dados agregados brasileiros

### 2.1 Impressões digitais comparecimento × share (Klimek, Yegorov, Hanel & Thurner, PNAS 2012)
Testa se o histograma bivariado (comparecimento, share do vencedor) por unidade apresenta "cauda" rumo a
(100%, 100%) e bimodalidade, modelando "incremental" e "extreme fraud". **Falsos positivos no Brasil:** o voto
é obrigatório (comparecimento comprimido em 70–85%, distribuição não Gaussiana por desenho); seções pequenas
(≤50 eleitores, zona rural, aldeias, presídios, hospitais, seções de trânsito) geram pontos em (100%, 100%)
por mera variância binomial; seções agregadas misturam populações. **Controle:** usar seções com `QT_APTOS ≥ 100`
e `ST_SECAO_INSTALADA = S`, excluir trânsito e seções com `QT_APTOS` atípico; comparar contra simulação
binomial-beta calibrada por UF/porte, não contra Gaussiana. **FDR:** o método é de forma global, não gera p por
seção; não usar para ranquear seções. **Não apropriado** para alegar qualquer coisa a nível individual; útil
apenas como descritivo UF vs UF e turno vs turno.

### 2.2 Últimos dígitos / dígitos (Beber & Scacco 2012; Mebane 2006–2013 "2BL")
Testa uniformidade do último dígito (Beber–Scacco) ou Benford no segundo dígito (Mebane) em contagens por
unidade; desvios sugerem números fabricados por humanos. **Falsos positivos:** contagens pequenas (<10 votos
são a maioria das linhas de `votacao_secao` para candidatos a deputado) violam a premissa de uniformidade;
agregados mun/zona não têm razão alguma para seguir Benford (Deckert, Myagkov & Ordeshook 2011 mostram que 2BL
falha em dados limpos); totais com arredondamento zero. **Controle:** só contagens ≥ 100 (último dígito) e
só por cargo/turno; simular a distribuição esperada a partir dos próprios dados (bootstrap). **FDR:** uma
estatística por UF×cargo, correção BH sobre as ~30–160 comparações. **Não apropriado** para votos por
seção no Brasil, cuja contagem é eletrônica, sem transcrição manual: o mecanismo que o teste captura
(digitação humana) não existe na urna; só seria relevante para BU transcrito, que não é o caso em 2026.

### 2.3 Fluxos de voto (Myagkov, Ordeshook & Shakin 2009)
Regressão ecológica de votos do candidato no 2º turno sobre comparecimento e votos no 1º: coeficiente > 1 em
"votos adicionais" (eleitores que não vieram no 1º) indica incremento artificial. **Falsos positivos:** falácia
ecológica; realocação de eleitores entre seções (agregação diferente entre turnos); voto em trânsito concentrado
no 2º; mobilização diferencial regional legítima. **Controle:** pareamento rígido de seção entre turnos (mesmo
`NR_LOCAL_VOTACAO`, mesmo `QT_APTOS`), baseline por UF e porte, intervalos (bounds de Duncan–Davis), não ponto.
**FDR:** resíduos por seção padronizados contra a regressão da própria UF; BH por UF. **Não apropriado** para
afirmar transferência individual A→B; apenas resíduos agregados "fora do padrão estadual".

### 2.4 "Urnas cheias" (ballot stuffing proxy)
Testa seções com comparecimento ≈ 100% ou > aptos, ou com share extremo em comparecimento extremo.
**Falsos positivos:** `QT_COMPARECIMENTO > QT_APTOS` pode decorrer de eleitores com transferência temporária
(TTE) ou mesários votando fora da seção de origem (verificar `leiame.pdf`); seções ≤50; presídios e aldeias com
comparecimento quase total. **Controle:** `perfil_eleitor_secao` (não baixado) e `eleitorado_local_votacao`;
excluir seções de trânsito; baseline por porte. **FDR:** p empírico por UF×porte, BH. Comparecimento > aptos é
**documental**, não forense: o BU mostra se o número foi o da urna.

### 2.5 Correlação nulos/brancos × share de candidato
Testa correlação espacial entre taxa de nulos e share do candidato (teoria: anulação seletiva ou "spoiling").
**Falsos positivos:** nulos correlacionam fortemente com escolaridade, renda e ruralidade, que correlacionam
com voto; seções agregadas; voto de protesto regional. **Controle:** correlação parcial dentro de município
(efeitos fixos de município ou zona), nunca correlação bruta nacional. **FDR:** por município com ≥ 20 seções.
**Não apropriado** sem covariáveis socioeconômicas por seção (não disponíveis nos arquivos atuais; só com
`perfil_eleitor_secao`). Em urna eletrônica o nulo é digitado pelo eleitor: o mecanismo clássico (anulação de
cédula pela mesa) não existe.

### 2.6 Saltos discretos / descontinuidades
Testa acumulação anômala em limiares (ex.: share exatamente 50%, comparecimento redondo, picos em números
inteiros). **Falsos positivos:** seções pequenas produzem frações "redondas" naturalmente (50 votos → múltiplos
de 2%); seções com `QT_APTOS` padronizado pelo cartório (ex.: 400) geram picos legítimos. **Controle:** comparar
histograma observado com histograma gerado por bootstrap binomial dado `QT_APTOS` e share do município.
**FDR:** teste único por UF×cargo; não ranqueia seções.

### 2.7 Seções gêmeas (distribuições idênticas em seções distintas)
Testa pares de seções com vetor de votos idêntico ou quase (distância L1 ≈ 0, similaridade de cosseno ≈ 1) com
`QT_COMPARECIMENTO` alto. **Falsos positivos:** seções pequenas (poucos candidatos com votos → vetores
esparsos iguais por acaso); seções no mesmo local com mesmo eleitorado-tipo; seções agregadas duplicadas no
arquivo (erro documental, não forense). **Controle:** exigir `QT_COMPARECIMENTO ≥ 200` e cargo proporcional
(Dep. Federal, vetor longo); calcular probabilidade de coincidência via permutação dentro do município.
**FDR:** número de pares é O(n²); usar q-valor sobre pares candidatos pré-filtrados por hashing. Um par gêmeo
em arquivos derivados é, antes de tudo, suspeita de **duplicação na exportação**: checar BU das duas seções.

### Nota geral de ceticismo
Toda a literatura acima foi desenvolvida para cédulas de papel contadas e transcritas manualmente. No Brasil
a contagem é eletrônica e o BU é emitido pela própria urna; o ponto de fragilidade testável com dados abertos
não é a "mão humana" na contagem, mas (a) a transmissão/totalização (BU × totalização) e (b) a integridade do
equipamento (hashes/logs). Nenhum teste da Seção 2 toca (a) ou (b). Por isso, nenhum resultado da Seção 2 pode
ser classificado acima de **estatístico**.

---

## 3. Especificação da matriz de risco

Arquivo alvo: `analysis/outputs/tables/risk_matrix.parquet` (+ `.csv`), uma linha por (unidade, finding_type).

| Coluna | Tipo | Definição |
|--------|------|-----------|
| `uf` | str | `SG_UF` |
| `municipio` | str | `CD_MUNICIPIO` (+ `NM_MUNICIPIO` em coluna auxiliar) |
| `zona` | int | `NR_ZONA` |
| `secao` | int/null | `NR_SECAO`; null quando o achado é mun/zona |
| `nr_turno` | int | 1 ou 2 |
| `cd_cargo` | int | `CD_CARGO` |
| `finding_type` | enum | `balanco`, `agregacao`, `divergencia_fontes`, `unanimidade`, `comparecimento_extremo`, `comparecimento_gt_aptos`, `residuo_virada`, `nulos_x_share`, `secao_gemea`, `salto_discreto`, `secao_anulada`, `apu_separada`, `demografia_impossivel` |
| `classe` | enum | `documental` \| `estatistico` \| `forense` — com os arquivos atuais **nenhuma linha** pode receber `forense` |
| `severity` | int 1–5 | rubrica abaixo |
| `metric_value` | float | valor da métrica bruta (ex.: share, comparecimento, delta) |
| `n_eleitores` | int | `QT_APTOS` da unidade (para filtrar pequenas) |
| `p_empirico` | float | percentil da métrica na distribuição de referência (mesma UF, mesmo porte de `QT_APTOS`, mesmo turno/cargo), via permutação ou bootstrap; declarar `reference_group_id` |
| `q_fdr` | float | q-valor Benjamini–Hochberg dentro de cada `finding_type` × `nr_turno` × `cd_cargo` (nunca pool global) |
| `risk_score` | float [0,1] | `w1·severity/5 + w2·(1-q_fdr) + w3·log10(n_eleitores)/3`, pesos em `config.yaml`; **não** é probabilidade |
| `flags_exclusao` | list | motivos para desconto: `secao_pequena`, `voto_transito`, `secao_agregada`, `local_especial` (presídio/aldeia/hospital por `NM_LOCAL_VOTACAO`), `nao_instalada` |
| `source_query_id` | str | id da query/script que gerou a linha |
| `what_bu_would_resolve` | str | texto curto: o que o BU / correspondência / log confirmaria ou refutaria |

### Rubrica de severidade
| Nível | Critério | Exemplo |
|-------|----------|---------|
| 1 | Anomalia estatística isolada, `q_fdr ≥ 0,05`, unidade pequena ou flag de exclusão presente | Seção de 40 eleitores com 100% |
| 2 | Anomalia estatística com `q_fdr < 0,05`, unidade ≥ 100 eleitores, sem flag de exclusão | Comparecimento no percentil 99,9 da UF |
| 3 | Duas ou mais anomalias independentes na mesma unidade **ou** inconsistência documental de pequena magnitude (≤ 0,1% dos votos) | Unanimidade + resíduo de virada; Σ seções ≠ zona por poucos votos |
| 4 | Inconsistência documental que viola identidade exata em magnitude relevante **ou** divergência entre arquivos oficiais do mesmo `DT_GERACAO` | `QT_COMPARECIMENTO > QT_APTOS` com diferença > 5% |
| 5 | Divergência entre BU (fonte primária) e totalização — **só atribuível após download do BU** | Reservado; não ocorre nesta fase |

Regras: severity ≥ 4 nunca decorre só de teste estatístico. `risk_score` só ordena a fila de auditoria de
BU; não aparece no sumário executivo como "chance de" nada.

---

## 4. Guia de linguagem obrigatório

**Permitido**
- "inconsistência documental" / "inconsistência de arquivo" (falha de identidade ou agregação)
- "anomalia estatística" / "desvio em relação ao padrão da UF" / "valor extremo (percentil X)"
- "requer auditoria de BU" / "requer confronto com correspondência efetivada" / "não auditável com os dados atuais"
- "estimativa ecológica agregada" / "intervalo de transferência aparente" (viradas)
- "sob H0 de [modelo], a frequência esperada é ..." (sempre nomeando o modelo)
- "não verificado" / "inconclusivo"

**Proibido**
- "fraude", "manipulação", "adulteração", "urna viciada", "voto roubado", "resultado falso" — em qualquer forma, inclusive negada ("não há fraude") ou condicional
- "probabilidade de fraude", "% de chance de irregularidade", "índice de suspeição"
- "suspeito", "comprovado", "evidência de irregularidade" (sem BU/log/hash não há evidência forense)
- "a urna X foi ...", "o candidato Y recebeu votos indevidos"
- atribuição de intenção ou agente ("alguém", "operadores")
- estimar fluxo A→B como se fosse voto individual ("X eleitores de A votaram em B")
- qualquer número sem `source_query_id`

Toda frase que descrever um achado deve conter: classe (`documental`/`estatístico`), magnitude, grupo de
referência e o que resolveria (`what_bu_would_resolve`).

---

## 5. Backlog de downloads mínimos (não executar agora)

Tamanhos obtidos via `HEAD` no CDN em 2026-10-28 (sem download). Portal: https://dadosabertos.tse.jus.br/dataset/?q=2026
(18 datasets 2026). Datasets relevantes:
- Boletim de Urna: https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna (56 recursos: ZIP + `.sha512` por UF + ZZ; só 1º turno listado em 2026-10-28)
- Arquivos transmitidos para totalização (bu, imgbu, logjez, rdv, vscmr): https://dadosabertos.tse.jus.br/dataset/resultados-2026-arquivos-transmitidos-para-totalizacao (28 ZIPs por UF, 1º turno)
- Correspondências esperadas/efetivadas 1º turno: https://dadosabertos.tse.jus.br/dataset/resultados-2026-correspondencias-esperadas-e-efetivadas-1-turno (168 recursos); 2º turno: `...-2-turno`
- Logs Gedai 1º/2º turno: `resultados-2026-logs-do-sistema-de-preparacao-das-urnas-eletronicas-gedai-{1,2}-turno`
- Eleitorado 2026 (perfil por seção): https://dadosabertos.tse.jus.br/dataset/eleitorado-2026
- Comparecimento e abstenção 2026: https://dadosabertos.tse.jus.br/dataset/comparecimento-e-abstencao-2026
- Relatório de Totalização por UF (já listado em `resultados-2026`, não baixado)

| Prioridade | Item | Justificativa | Tamanho estimado |
|-----------|------|---------------|------------------|
| P1 | `bweb_1t_{UF}.zip` (BU em CSV) **só das UFs com seções no top-N do `risk_score`**, + `.sha512` | Único arquivo que converte "divergência" em achado forense (BU × `votacao_secao`). CSV, processável em DuckDB | AC = 17 MB (~1,3 mil seções) ⇒ ~13 KB/seção; SP ≈ 1,3 GB; Brasil ≈ 6–7 GB. Top-3 UFs ≈ 2,5 GB |
| P1 | `CESP_1t_{UF}` + `CEFT_1t_{UF}` (correspondência esperada/efetivada) para as mesmas UFs | Resolve `ST_SECAO_ANULADA`, urna substituída, modelo real da urna, seções agregadas | ~0,4 MB cada por UF; Brasil inteiro < 50 MB — **baixar todo**, custo trivial |
| P2 | `perfil_eleitor_secao_2026_{UF}.zip` | Baseline por seção (faixa etária, gênero, escolaridade) para controles em 2.4/2.5 e para demografia | SP = 630 MB; Brasil ≈ 3 GB. Começar pelas top-3 UFs |
| P2 | `perfil_comparecimento_abstencao_2026.zip` (+ TTE) | Explica comparecimento > aptos e seções de trânsito | 229 MB |
| P2 | Relatório de Totalização `{UF}.zip` | Fonte oficial agregada independente dos CSVs para cross-check de agregação | pequeno (não medido) |
| P3 | `bu_imgbu_logjez_rdv_vscmr_2026_1t_{UF}.zip` | RDV e log da urna por seção. Só para seções específicas já com BU divergente; formato binário/ASN.1, exige parser | AC = 394 MB; **SP = 20,1 GB**; Brasil estimado > 100 GB. **Não baixar por UF**; avaliar extração seletiva |
| P3 | Logs Gedai | Preparação de urnas; relevante só se correspondência indicar substituições anômalas | ~1 MB por UF/turno |
| — | BU 2º turno | Ainda não publicado no dataset em 2026-10-28; reavaliar | — |

Critério de disparo: baixar P1 apenas após a matriz de risco ter ≥ 1 linha com severity ≥ 3 e `q_fdr < 0,01`
em seção ≥ 100 eleitores sem flag de exclusão. Sem isso, o custo não se justifica e a conclusão correta é
"nenhuma inconsistência documental relevante; anomalias estatísticas dentro do esperado sob FDR".
