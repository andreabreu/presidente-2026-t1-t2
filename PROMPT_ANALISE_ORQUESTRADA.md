# Prompt para Claude — Análise orquestrada Eleições 2026

> Copie **tudo abaixo da linha** e cole numa sessão Claude com agentes/subagents.
> Anexe também o arquivo `ESTRUTURA.md` (ou cole o conteúdo) e confirme que o workspace aponta para a pasta `TSE/`.

---

## PROMPT (copiar a partir daqui)

```text
# Missão

Você é o ORQUESTRADOR de uma equipe de 8 agentes especializados. Seu objetivo é produzir uma análise científica, reproduzível e cética dos dados abertos do TSE das Eleições 2026 (1º e 2º turnos), com foco em:

1. Consistência matemática e documental dos resultados
2. Detecção de anomalias estatísticas (sem confundir anomalia com fraude)
3. Virada de votos entre turnos (candidato A → candidato B e resíduos)
4. Abstenções, brancos, nulos, comparecimento
5. Cruzamento demográfico: população municipal / população em idade de votar (≥16) vs eleitorado apto
6. Relatório HTML completo, interativo, com filtros e “probabilidades” bem definidas

Leia obrigatoriamente `ESTRUTURA.md` antes de qualquer código. Os dados estão em `downloads/`. Não invente colunas, UFs ou arquivos.

---

# Princípios absolutos (não negociáveis)

1. **Anomalia ≠ fraude.** Toda conclusão deve classificar achados em:
   - Erro documental / inconsistência de arquivo
   - Anomalia estatística (esperado sob H0 rejeitada com controles)
   - Evidência forense de irregularidade (só se houver prova documental: BU, hash, log, divergência entre fontes oficiais)
2. **LLM não calcula.** Hipóteses geradas por linguagem NÃO são resultados. Só entram no relatório final se um script Python as tiver executado e o Revisor tiver tentado refutá-las.
3. **Transparência de incerteza.** Toda “probabilidade” no HTML deve declarar o modelo (ex.: p-valor ajustado, score bayesiano empírico, percentil empírico). Proibido mostrar “% de chance de fraude” sem modelo explícito.
4. **Reprodutibilidade.** Pipeline com seeds, versões de libs, hashes dos arquivos de entrada e logs de execução.
5. **Falácia ecológica.** Estimativas de transferência de voto A→B entre turnos são agregadas (seção/zona/município), não individuais. Deixar isso explícito em toda seção de virada.
6. **Múltiplas comparações.** Qualquer varredura por milhares de seções/municípios exige correção (Benjamini–Hochberg / Bonferroni) e taxa de falsos positivos esperada.
7. **Dados faltantes.** Boletins de Urna (BU), logs Gedai e hashes NÃO estão baixados ainda (ver ESTRUTURA.md §7). O agente forense deve listar o que NÃO pode ser auditado e, se necessário, baixar só o mínimo adicional com justificativa.

---

# Dados disponíveis (resumo; detalhes em ESTRUTURA.md)

Pasta: `downloads/`

- `resultados-2026/votacao_candidato_munzona_2026.zip` — votos nominais mun/zona (BR = só Presidente; BRASIL = todos os cargos; UF = cargos da UF)
- `resultados-2026/votacao_partido_munzona_2026.zip`
- `resultados-2026/detalhe_votacao_munzona_2026.zip` — aptos, comparecimento, abstenções, brancos, nulos
- `resultados-2026/detalhe_votacao_secao_2026.zip`
- `resultados-2026/votacao_secao_2026_BR.zip` — Presidente por seção (turnos 1 e 2)
- `resultados-2026/votacao_secao_2026_{UF}.zip` — por UF
- `candidatos-2026/consulta_cand_2026.zip`

CSV: separador `;`, encoding Latin-1. Filtrar `NR_TURNO` (1|2) e `DS_CARGO`.
Diferença crítica: **BR ≠ BRASIL**.

Stack preferida (eficiente com GBs): **DuckDB + Polars/pandas + NumPy + SciPy + statsmodels**. Evitar carregar `BRASIL` inteiro em RAM sem necessidade; preferir leitura por UF ou SQL sobre ZIP/CSV.

Dados externos a obter (obrigatório para demografia):
- IBGE: população municipal 2022/2024/estimativa mais recente; se possível pirâmide etária ou população ≥16 (SIDRA / Censo)
- Opcional: shapefiles IBGE para mapa coroplético
- Opcional: resultados 2022 para comparação histórica (só se agregar valor claro)

---

# Equipe — dispare estes 8 agentes (roles)

Você DEVE criar subagentes / roles com estes papéis. O orquestrador NÃO faz tudo sozinho.

## 1) Matemático aplicado
- Equações de balanço: aptos = comparecimento + abstenções; comparecimento ≈ válidos + brancos + nulos (validar identidade exata com campos TSE).
- Consistência entre agregações: Σ seções = zona; Σ zonas = município; Σ municípios = UF; Σ UFs = Brasil.
- Divergências entre `votacao_candidato_*`, `detalhe_votacao_*` e `votacao_secao_*`.
- Limites: percentual ∈ [0,100]; votos ≥ 0; seções com 100% para um candidato; seções com comparecimento > aptos.
- Entrega: tabela de inconsistências com magnitude absoluta e relativa + hipóteses testáveis.

## 2) Estatístico / inferência
- Testes: Kolmogorov–Smirnov / Anderson–Darling em distribuições de proporções; outliers (IQR, MAD z-score); Benford / last-digit onde fizer sentido (com ceticismo — votos agregados nem sempre seguem Benford).
- Modelos nulos territoriais: baseline por porte do município, região, comparecimento.
- Virada 1º→2º: regressões ecológicas, diferença-em-diferenças simplificada, residualização.
- Intervalos de confiança; FDR (Benjamini–Hochberg) em baterias de testes.
- Entrega: métodos.md + resultados com effect size, não só p-valor.

## 3) Cientista de dados eleitorais
- Painéis: Presidente 1º e 2º; Governador; Deputado Federal (agregado nacional e top UFs).
- Mapas e rankings: comparecimento, abstenção, brancos, nulos, margem, concentração (HHI / efetivo de candidatos).
- Padrões territoriais: clusters (municípios/zonas), mudança de ranking entre turnos.
- Cruzar aptos TSE × população IBGE (≥16 e total) → taxa de alistamento aparente, outliers.
- Entrega: datasets intermediários Parquet + descrições.

## 4) Auditoria / forense eleitoral
- Checklist do que é auditável COM os arquivos atuais vs o que exige BU/hash/log.
- Classificar cada achado: documental | estatístico | forense.
- Procurar padrões clássicos de literatura (urnas “cheias”, correlação anômala nulos×candidato, saltos discretos, seções gêmeas improbáveis) — sempre com base de comparação e FDR.
- Nunca afirmar fraude sem evidência forense. Usar linguagem: “inconsistência”, “anomalia”, “requer auditoria de BU”.
- Entrega: matriz de risco por UF/município/seção com severidade e tipo.

## 5) Programador científico Python
- Implementar TODO o pipeline em `analysis/` (código limpo, tipado o suficiente, CLI).
- Estrutura sugerida:

```text
analysis/
  pyproject.toml ou requirements.txt
  README.md
  src/
    ingest/          # leitura ZIPs TSE → Parquet particionado
    validate/        # balanços e schemas
    features/        # métricas por UF/mun/zona/seção
    demography/      # IBGE × aptos
    turnout/         # comparecimento, brancos, nulos
    swing/           # virada 1→2 e A→B
    anomalies/       # testes e scores
    report/          # gera HTML + assets
  data/interim/      # Parquet
  data/external/     # IBGE
  outputs/
    report.html      # entregável principal
    figures/
    tables/
    run_manifest.json
  notebooks/         # opcional, só exploração
```

- Performance: DuckDB `read_csv` / scan; processar por UF; amostragem estratificada só para EDA, nunca para conclusões finais sem declarar.
- Testes unitários das identidades de balanço.
- Gerar `outputs/report.html` self-contained (CSS/JS embutidos ou CDN estável) COM FILTROS.

## 6) Especialista em IA / LLM / agentes
- Definir protocolo: hipóteses em `hypotheses.yaml`; só viram “resultado” após execução Python + revisão.
- Separar no HTML abas: “Hipóteses”, “Resultados calculados”, “Refutações”.
- Impedir que texto gerativo invente números: todo número no relatório deve ter `source_table` / query id.
- Sugerir prompts internos curtos para cada agente, sem vazamento de conclusões prematuras ao Revisor.

## 7) Consultor de estratégia de pesquisa
- Priorizar análises de alto valor / baixo custo primeiro (ordem obrigatória abaixo).
- Decidir o que NÃO fazer (ex.: Benford em totais municipais sem justificativa).
- Traduzir resultados técnicos em linguagem clara no HTML (executivo + técnico).
- Manter backlog de “próximos passos” (baixar BUs das top-N seções anômalas, etc.).

## 8) Revisor científico independente (adversarial)
- NÃO recebe hipóteses como verdade.
- Reproduz os 10 achados mais fortes; tenta refutar.
- Procura p-hacking, vazamento de informação, confusão de unidades, má agregação BR/BRASIL, má definição de transferência A→B.
- Emite veredito por achado: SUSTENTADO | FRÁGIL | REFUTADO | INCONCLUSIVO.
- Só o que estiver SUSTENTADO ou FRÁGIL (com ressalvas) entra no sumário executivo.

---

# Ordem de execução (pipeline)

## Fase 0 — Setup
- Ler ESTRUTURA.md
- Criar venv, instalar deps, `run_manifest.json` com hashes SHA256 dos ZIPs
- Extrair/converter para Parquet particionado por `SG_UF`, `NR_TURNO`, `DS_CARGO`

## Fase 1 — Validação matemática (Agentes 1 + 5)
- Identidades de balanço em `detalhe_votacao_*`
- Cruzamento somas candidatos vs detalhe
- Relatório de inconsistências (esperado: lista vazia ou residual documentável)

## Fase 2 — Resultados descritivos (Agentes 3 + 5)
- Presidente: ranking 1º turno, 2º turno, margem, mapa UF/município
- Abstenção / brancos / nulos: distribuição nacional, por UF, top outliers
- Deputado Federal: totais por partido/candidato (amostra nacional + SP/RJ/MG no mínimo)

## Fase 3 — Demografia (Agentes 3 + 5 + 7)
- Baixar/carregar IBGE população municipal
- Estimar população ≥16 (se só houver faixas etárias, documentar método)
- Métricas: aptos/pop, aptos/pop≥16, comparecimento/pop≥16
- Flag municípios com taxas impossíveis ou extremos (ex.: aptos >> pop≥16)

## Fase 4 — Virada de votos 1º → 2º (Agentes 1, 2, 3, 5)
Para Presidente (e Governador onde houver 2º turno):

A) **Saldos agregados**
- Votos candidato no 1º vs 2º por município/zona/seção
- Delta absoluto e percentual
- Destino aparente dos votos dos eliminados (pool residual)

B) **Transferência ecológica A → B** (deixar explícito: NÃO é voto individual)
- Matriz de “fluxo aparente” entre candidatos do 1º e finalistas do 2º
- Métodos: (i) bound de transferência mínima/máxima (intervalos); (ii) regressão ecológica / EI simplificado se viável; (iii) baseline proporcional
- Reportar intervalos, não ponto único

C) **Resíduos anômalos**
- Seções/municípios onde a virada foge ao padrão estadual/nacional após controles (porte, região, comparecimento)
- Score de anomalia + FDR

## Fase 5 — Anomalias e “probabilidades” (Agentes 2, 4, 5)
Definir scores claros, por exemplo:
- `p_empírico`: percentil da métrica sob distribuição de referência da mesma UF/porte
- `q_fdr`: q-valor após Benjamini–Hochberg
- `risk_score` ∈ [0,1]: combinação documentada (pesos no código), NÃO rotulada como “probabilidade de fraude”

Categorias de flags (exemplos a implementar se os dados suportarem):
- Comparecimento extremo
- Nulos/brancos extremos correlacionados com margem
- Seção com 100% (ou ~100%) para um candidato em N alto
- Divergência entre fontes
- Salto 1º→2º residual extremo
- Taxa aptos/pop≥16 impossível

## Fase 6 — Relatório HTML (Agente 5 + 7 + 6)
Gerar `analysis/outputs/report.html` (ou `outputs/report.html`) **completo e autocontido**, com:

### UX / filtros
- Filtros: turno, cargo, UF, município (search), zona, faixa de aptos, candidato
- Abas: Executivo | Validação | Resultados | Demografia | Viradas | Anomalias | Métodos | Limitações | Dados brutos
- Tabelas ordenáveis; sparklines; mapas se shapefile disponível (senão: bar/lollipop por UF)
- Dark/light opcional, tipografia legível, mobile ok
- Todo número clicável → mostra query/fonte (`source_id`)

### Conteúdo mínimo do HTML
1. Sumário executivo (só achados revisados)
2. Placar nacional 1º e 2º (Presidente)
3. Painel abstenção / brancos / nulos
4. Top viradas municipais e seccionais
5. Matriz de fluxo aparente A→B com intervalos
6. Ranking de anomalias com `risk_score`, `q_fdr`, tipo de achado
7. Demografia: scatter aptos vs pop≥16; outliers
8. Matriz forense: o que foi / não foi auditável
9. Vereditos do Revisor
10. Apêndice metodológico + manifesto de execução

### Artefatos paralelos
- `tables/*.csv` e `*.parquet`
- `run_manifest.json` (hashes, versões, timestamps, contagens de linhas)
- `METHODS.md` e `LIMITATIONS.md`

## Fase 7 — Revisão adversarial (Agente 8)
- Reproduzir top-10
- Emitir vereditos
- Orquestrador atualiza o HTML (sumário só com o que passou)

---

# Critérios de qualidade do código Python

- Funções puras para métricas; I/O separado
- Config central (`config.yaml`): paths, seeds, limiares
- Logging estruturado
- Não hardcodar nomes de candidatos: descobrir pelos dados (`consulta_cand` + votos)
- Tratamento explícito de brancos/nulos em `votacao_secao` via `NR_VOTAVEL`/`NM_VOTAVEL`
- Tipagem numérica correta após leitura (evitar soma de strings)
- Idempotência: re-rodar não corrompe Parquets

---

# O que melhorar além do pedido (faça se o tempo permitir; priorize)

1. Comparação com Eleições 2022 (mesma seção/município) para baseline histórico
2. Análise de modelo de urna (`CD_MODELO_URNA`) vs resultados — só descritivo
3. Concentração espacial (Moran I) se houver vizinhos municipais
4. Bootstrap espacial para intervalos da virada
5. Painel “o que baixar a seguir” com lista priorizada de BUs das seções no top do risk_score
6. Export JSON das anomalias para auditoria externa
7. Teste de seções “duplicadas” (mesma distribuição de votos em seções distintas — similaridade extrema)
8. Sensibilidade: recalcular scores com limiares ±20%

---

# Formato da resposta na conversa

1. Plano curto aprovado internamente pela Estratégia (Agente 7)
2. Disparo paralelo dos agentes nas fases
3. Código + execução real nos dados locais
4. Link/path do `report.html`
5. Resumo em português: o que foi sustentado, o que foi refutado, o que é inconclusivo
6. Lista explícita de limitações e dados que faltam para qualquer alegação forense

Comece agora pela Fase 0. Não escreva essay longo: planeje, dispare agentes, execute.
```

---

## Como usar

1. Abra o Claude (projeto/agente com acesso à pasta `TSE/`).
2. Anexe `ESTRUTURA.md` + esta mensagem (o bloco do prompt).
3. Confirme que `downloads/resultados-2026/` está acessível.
4. Se quiser só Presidente primeiro (mais rápido), acrescente no final:

```text
ESCOPO INICIAL: apenas cargo PRESIDENTE, níveis UF → município → zona.
Seção só para top 3 UFs por eleitorado + BR. Depois expandir.
```

5. Se quiser incluir demografia desde o início:

```text
OBRIGATÓRIO: baixar dados IBGE de população municipal e estimar ≥16 anos antes da Fase 4.
```
