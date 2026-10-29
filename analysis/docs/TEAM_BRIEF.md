# Brief comum para agentes de análise (leia antes de codar)

Working dir: /Users/andreabreu/Developer/TSE/analysis. Python: `.venv/bin/python` (duckdb 2.0, polars, pandas, pyarrow, numpy, scipy, statsmodels, plotly, pyyaml). Pacote `tse` instalado editável: `.venv/bin/python -m tse.<modulo>`.

Leia obrigatoriamente: ../ESTRUTURA.md, docs/STRATEGY.md (nomes de tabelas = source_id), docs/FORENSIC_CHECKLIST.md (linguagem permitida), hypotheses.yaml (se existir; referencie ids H..).

## Dados (Parquet, hive)
`data/interim/<dataset>/scope=<AC..TO|BR|BRASIL>/NR_TURNO=<1|2>/CD_CARGO=<n>/*.parquet`
Datasets: votacao_secao (27 UF + BR; sem BRASIL), votacao_candidato_munzona, votacao_partido_munzona, detalhe_votacao_munzona, detalhe_votacao_secao (BR, BRASIL, UFs; ZZ vazio), consulta_cand.
Helper: `from tse.io import connect, scan` — `scan(dataset, scope=None, turno=None, cargo=None, conn=None, engine="duckdb"|"polars")`. DuckDB 2.0: relações usam `.fetchall()`/`.df()`/`.pl()`.
Tipos: QT_* BIGINT; NR_TURNO, NR_ZONA, NR_SECAO, CD_MUNICIPIO (int, sem zero à esquerda), CD_CARGO, NR_CANDIDATO, NR_VOTAVEL, NR_PARTIDO INTEGER; resto VARCHAR.
CD_CARGO: 1 Presidente, 3 Governador, 5 Senador, 6 Dep. Federal, 7 Dep. Estadual, 8 Dep. Distrital. Join por CD_CARGO (DS_CARGO tem caixa diferente entre arquivos). Turno 2 só cargos 1 e 3.
BR ≠ BRASIL: BR = só Presidente; BRASIL = todos os cargos nacional. Nunca somar escopos entre si. Para Presidente use scope=BR; para outros cargos use scope=<UF> ou BRASIL.
Brancos/nulos em votacao_secao: via NR_VOTAVEL/NM_VOTAVEL (descobrir os códigos pelos dados, ex.: 95 branco, 96 nulo — VERIFICAR com query, não assumir).
Candidatos: não hardcodar nomes; descobrir via consulta_cand (scope=BR para Presidente) + votos.
Externo: data/external/ibge_populacao_municipal.parquet, data/external/crosswalk_tse_ibge.parquet (id_municipio_tse ↔ id_municipio_ibge). README em data/external/README_IBGE.md.

## Saídas (obrigatório)
- Tabelas em `outputs/tables/<source_id>.csv` E `.parquet`, nome snake_case conforme STRATEGY.md.
- Para CADA tabela, sidecar `outputs/tables/<source_id>.meta.json`: {source_id, title_pt, description_pt, script, hypothesis_ids, unit, n_rows, columns:{nome:descrição}, method, caveats_pt, generated_at}.
- Figuras opcionais em outputs/figures/ (plotly JSON preferido a PNG).
- Nenhum número em texto sem tabela de origem. Nunca usar palavra "fraude" afirmativa; usar "inconsistência", "anomalia estatística", "requer auditoria de BU".
- Intervalos/effect size sempre que houver p-valor. FDR (Benjamini–Hochberg) em qualquer bateria de testes; reportar q_fdr.
- Código limpo: funções puras para métricas, I/O separado, constantes nomeadas, sem comentários óbvios. Config em config.yaml (`from tse.config import load_config`). Seed = config['seed'].
- Testes em tests/ para identidades e funções puras. Rodar `.venv/bin/pytest tests -q` ao final.
- Logs em logs/<modulo>.log. Não editar módulos de outros agentes (ingest/, io.py, manifest.py, demography/ibge_download.py, hypotheses.py).
- Ao terminar, escrever `outputs/notes/<modulo>.md` (PT-BR, ≤80 linhas): o que foi calculado, principais números com source_id, hipóteses testáveis geradas, limitações.
