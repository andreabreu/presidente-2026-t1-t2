# Dados externos IBGE — população municipal e crosswalk TSE↔IBGE

Gerado por `src/tse/demography/ibge_download.py` (CLI: `.venv/bin/python -I -m tse.demography.ibge_download [--force]`).
Log em `logs/ibge.log`. Respostas brutas em `data/external/raw/` (somente dados; nada é executado a partir dali).

## Arquivos

### `ibge_populacao_municipal.parquet` (5.571 linhas)

| coluna | descrição |
|---|---|
| `id_municipio_ibge` | código IBGE de 7 dígitos |
| `nome_municipio`, `sigla_uf` | nome oficial e UF (API Localidades do IBGE) |
| `pop_total` | população residente estimada (SIDRA tabela 6579, variável 9324, período `last`) |
| `pop_total_ano` | ano da estimativa (2026 na execução de 2026-10-28; o pipeline sempre pega o último ano publicado) |
| `pop_16mais` | população residente com 16 anos ou mais, Censo 2022 |
| `pop_16mais_ano` | 2022 |
| `pop_16mais_metodo` | identificador do método (abaixo) |
| `chave_nome_uf` | `NOME SEM ACENTO EM MAIÚSCULAS|UF`, para casamento por nome como fallback |

### `crosswalk_tse_ibge.parquet` (5.570 linhas)

Colunas: `id_municipio_ibge` (int), `id_municipio_tse` (int), `nome`, `sigla_uf`, `chave_nome_uf`.
Sem duplicatas em nenhum dos dois códigos.

## Fontes

| dado | URL |
|---|---|
| Estimativas da população (tabela 6579) | `https://apisidra.ibge.gov.br/values/t/6579/n6/all/v/9324/p/last?formato=json` |
| Censo 2022 por idade (tabela 9514), uma requisição por UF | `https://apisidra.ibge.gov.br/values/t/9514/n6/in n3 {UF}/v/93/p/2022/c2/6794/c287/{idades}/c286/113635?formato=json` |
| Lista de municípios (DTB via API Localidades) | `https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado` |
| Crosswalk TSE↔IBGE | `https://raw.githubusercontent.com/betafcc/Municipios-Brasileiros-TSE/master/municipios_brasileiros_tse.csv` |

Dados do IBGE são de uso livre com citação da fonte (IBGE). O repositório `betafcc/Municipios-Brasileiros-TSE`
**não declara licença** e foi atualizado pela última vez em 2018-11; trata-se de uma compilação de dados públicos do TSE
(códigos de município) e do IBGE. O arquivo foi validado contra a lista atual do IBGE: 5.570/5.571 códigos casam.

## Método para população com 16 anos ou mais

A tabela 9514 oferece idades simples e grupos quinquenais por município. `pop_16mais` é a **soma exata** de:

- idades simples 16, 17, 18 e 19 anos (categorias 6573, 6574, 6575, 6576);
- grupos quinquenais de 20–24 a 95–99 anos (93087…93098, 49108, 49109, 60040, 60041);
- 100 anos ou mais (6653).

Sexo = Total (6794); forma de declaração da idade = Total (113635). Não houve rateio de grupo 15–19.
Como numerador (Censo 2022) e denominador (estimativa 2026) têm anos distintos, a razão `pop_16mais/pop_total`
é apenas indicativa; para proporções estritas usar a população total do Censo 2022 (variável 93, categoria Total).

## Verificações (execução 2026-10-28)

- municípios: 5.571 (5.570 + Boa Esperança do Norte/MT, código 5101837, instalado em 2025)
- soma `pop_total` (2026): 214.211.951
- soma `pop_16mais` (2022): 160.131.985
- razão 16+/total: mediana 0,764; 88,7% dos municípios entre 0,70 e 0,85; mínimos em municípios indígenas de RR (Uiramutã 0,39), máximos ~0,92 (Balbinos/SP, Catarina/CE)
- faltantes: `pop_16mais` ausente apenas em Boa Esperança do Norte/MT (não existia no Censo 2022)
- crosswalk: 5.570 municípios casados por código IBGE; Boa Esperança do Norte/MT sem código TSE no arquivo de 2018 —
  casar por `chave_nome_uf` ou completar manualmente quando o TSE publicar a correspondência.
