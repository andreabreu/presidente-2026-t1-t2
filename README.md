# Presidente 2026 — estudo 1º × 2º turno

Análise dos **dados abertos do TSE** sobre a eleição presidencial de 2026: placar, aritmética da virada, transferência de votos (estimativa ecológica), abstenções retomadas, urnas com voto concentrado e linha do tempo da apuração.

## Ver online

- **Início:** https://andreabreu.github.io/presidente-2026-t1-t2/
- **Estudo completo:** https://andreabreu.github.io/presidente-2026-t1-t2/estudo_t1_t2.html
- **Repositório:** https://github.com/andreabreu/presidente-2026-t1-t2

A pasta [`docs/`](docs/) contém o HTML estático do estudo (Plotly embutido; funciona offline).

## Dados do estudo (enxutos)

Em [`data/estudo/`](data/estudo/) (~37 MB) estão as tabelas e o JSON usados no relatório — **não** os zips brutos do TSE (~GBs).

| Arquivo | Conteúdo |
|---------|----------|
| `estudo_payload.json` | Números exatos renderizados no HTML |
| `desc_placar_presidente.csv` | Placar nacional por turno |
| `turnout_uf.csv` | Comparecimento / abstenção por UF |
| `swing_saldos_mun.csv` | Saldos T1→T2 por município |
| `swing_saldos_secao.parquet` | Saldos por seção (~499 mil urnas) |
| `swing_fluxo_matriz.csv` | Transferências estimadas |
| `swing_baseline_comparacao.csv` | Comparação vs cenário neutro |
| `swing_residuos_*.csv` | Resíduos / anomalias agregadas |
| `t2_apuracao_10min.csv` | Apuração em blocos de 10 min |
| `manifest.json` | Inventário do pacote |

## Baixar os microdados do TSE (opcional)

Fonte: [Resultados 2026 — Dados Abertos do TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026).

Para **regerar** o estudo do zero (incluindo nomes de locais e timestamps de BU), baixe para `downloads/resultados-2026/` (e candidatos em `downloads/candidatos-2026/`):

- `votacao_secao_2026_*.zip` (por UF + BR)
- `detalhe_votacao_secao_2026.zip`
- `detalhe_votacao_munzona_2026.zip`
- `votacao_candidato_munzona_2026.zip`
- `consulta_cand_2026.zip` → `downloads/candidatos-2026/`

Inventário local: [`downloads/README.md`](downloads/README.md).

Depois, no ambiente Python do projeto:

```bash
cd analysis
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m tse.ingest          # zips → parquet interim
# rode o restante do pipeline (features / swing / turnout) conforme config
.venv/bin/python -m tse.report.estudo   # gera docs/estudo_t1_t2.html
```

Quem só quer **consultar** os números do relatório: use `data/estudo/` ou o HTML em Pages — não precisa dos zips.

## Abrir localmente

```bash
open docs/estudo_t1_t2.html
```

## Regenerar só o HTML

Com as tabelas do pipeline já em `analysis/outputs/tables/`:

```bash
cd analysis
.venv/bin/python -m tse.report.estudo
```

Atualiza `analysis/outputs/estudo_t1_t2.html` e `docs/estudo_t1_t2.html`.

## O que o estudo cobre

| Seção | Conteúdo |
|------|----------|
| Placar | Votos por candidato no 1º e no 2º turno |
| Aritmética | “Pote” de votos soltos e % tomada por cada finalista |
| Abstenção | Retornos mínimos por urna e saldo de comparecimento |
| Transferências | Fluxo estimado (inferência ecológica) |
| Troca direta | Limites matemáticos — o pote basta sem troca |
| Estados / municípios | Viradas locais e excesso vs cenário neutro |
| Urnas zeradas / &lt;10% | Contagens, tipo de local e impacto no resultado |
| Linha do tempo | Boletins por minuto, margem acumulada, estabilidade |
| Anomalias | Resíduos fora do padrão e validações de soma |

## Limites

- Transferências entre grupos do 1º turno são **estimativas agregadas** (inferência ecológica), não o voto de pessoas.
- Os totais públicos permitem fechar a aritmética nacional e municipal; a conferência documental (BU impresso e registros das urnas) continua sendo o passo definitivo quando houver dúvida pontual.
- Estatística descreve padrões e raridades; não substitui auditoria documental.

## Estrutura do repositório

```
docs/                 # GitHub Pages (estudo HTML)
data/estudo/          # tabelas enxutas + payload do relatório
analysis/             # pipeline (código + testes)
downloads/            # zips do TSE (não versionados; ver README lá)
```

## Licença dos dados

Os microdados eleitorais são públicos, divulgados pelo TSE. Este estudo é uma análise independente; não é material oficial do Tribunal.
