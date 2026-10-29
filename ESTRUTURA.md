# Estrutura dos dados TSE — Eleições 2026

Documentação do material baixado em `downloads/` a partir do [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/).

| Item | Valor |
|------|--------|
| Fonte resultados | [Resultados - 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026) |
| Fonte candidatos | [Candidatos - 2026](https://dadosabertos.tse.jus.br/dataset/candidatos-2026) |
| CDN | `https://cdn.tse.jus.br/estatistica/sead/odsele/...` |
| Volume local | ~3,6 GB (ZIPs compactados) |
| Inventário de URLs | `downloads/links_votacao_2026.csv` |

---

## 1. Árvore de pastas

```text
TSE/
├── ESTRUTURA.md                          ← este documento
└── downloads/
    ├── README.md                         ← resumo curto
    ├── links_votacao_2026.csv            ← nome + URL de cada ZIP baixado
    ├── urls_votacao.txt                  ← lista só de URLs
    ├── resultados-2026.json              ← metadados CKAN (API package_show)
    ├── candidatos-2026.json              ← metadados CKAN
    ├── candidatos-2026/
    │   └── consulta_cand_2026.zip        ← cadastro de candidatos (~3,1 MB)
    └── resultados-2026/
        ├── votacao_candidato_munzona_2026.zip   ← votos nominais mun/zona (~449 MB)
        ├── votacao_partido_munzona_2026.zip     ← votos de legenda mun/zona (~22 MB)
        ├── detalhe_votacao_munzona_2026.zip     ← apuração agregada mun/zona (~3 MB)
        ├── detalhe_votacao_secao_2026.zip       ← apuração por seção (~224 MB)
        ├── votacao_secao_2026_BR.zip             ← Presidente por seção (~231 MB)
        └── votacao_secao_2026_{UF}.zip          ← 27 UFs, votos por seção
```

UFs presentes: `AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO` (+ `BR` para presidente).

---

## 2. Formato comum dos CSVs

Todos os CSVs oficiais do TSE nestes pacotes seguem o mesmo padrão:

| Propriedade | Valor |
|-------------|--------|
| Separador | `;` (ponto e vírgula) |
| Encoding | Latin-1 / ISO-8859-1 |
| Aspas | campos entre aspas duplas |
| Cabeçalho | primeira linha |
| Documentação interna | `leiame.pdf` dentro de cada ZIP |

**Atenção:** arquivos grandes (principalmente `votacao_secao` e `votacao_candidato`) ultrapassam o limite de linhas do Excel (~1.048.576). Use Python/pandas, DuckDB, Polars, Power Query ou banco de dados.

### Filtros principais

| Campo | Uso |
|-------|-----|
| `NR_TURNO` | `1` = 1º turno · `2` = 2º turno |
| `DS_CARGO` / `CD_CARGO` | cargo disputado |
| `SG_UF` | unidade da federação |
| `ANO_ELEICAO` | `2026` |

Os ZIPs **misturam 1º e 2º turno** no mesmo arquivo quando o cargo teve segundo turno (Presidente; Governador onde houve).

---

## 3. Conteúdo interno dos ZIPs

### 3.1 `votacao_candidato_munzona_2026.zip` (~449 MB)

Votação **nominal por candidato**, agregada por município e zona.

```text
leiame.pdf
votacao_candidato_munzona_2026_{UF}.csv   × 27 UFs
votacao_candidato_munzona_2026_BR.csv
votacao_candidato_munzona_2026_BRASIL.csv
```

- **`_BR.csv`**: só **Presidente** (turnos 1 e 2). Ex.: ~88 mil linhas (75.504 no 1º + 12.584 no 2º).
- **`_BRASIL.csv`**: **consolida todos os cargos de todas as UFs** num único CSV nacional (arquivo bem maior). Contém Presidente, Deputado Federal, Deputado Estadual, Deputado Distrital, Senador, Governador; turnos 1 e 2 onde aplicável.
- **`_{UF}.csv`**: cargos daquela UF. Exemplo SP (só 1º turno neste arquivo): Deputado Estadual, Deputado Federal, Senador, Governador.

**50 colunas:**

```text
DT_GERACAO, HH_GERACAO, ANO_ELEICAO, CD_TIPO_ELEICAO, NM_TIPO_ELEICAO,
NR_TURNO, CD_ELEICAO, DS_ELEICAO, DT_ELEICAO, TP_ABRANGENCIA,
SG_UF, SG_UE, NM_UE, CD_MUNICIPIO, NM_MUNICIPIO, NR_ZONA,
CD_CARGO, DS_CARGO, SQ_CANDIDATO, NR_CANDIDATO, NM_CANDIDATO,
NM_URNA_CANDIDATO, NM_SOCIAL_CANDIDATO,
CD_SITUACAO_CANDIDATURA, DS_SITUACAO_CANDIDATURA,
CD_DETALHE_SITUACAO_CAND, DS_DETALHE_SITUACAO_CAND,
CD_SITUACAO_JULGAMENTO, DS_SITUACAO_JULGAMENTO,
CD_SITUACAO_CASSACAO, DS_SITUACAO_CASSACAO,
CD_SITUACAO_DCONST_DIPLOMA, DS_SITUACAO_DCONST_DIPLOMA,
TP_AGREMIACAO, NR_PARTIDO, SG_PARTIDO, NM_PARTIDO,
NR_FEDERACAO, NM_FEDERACAO, SG_FEDERACAO, DS_COMPOSICAO_FEDERACAO,
SQ_COLIGACAO, NM_COLIGACAO, DS_COMPOSICAO_COLIGACAO,
ST_VOTO_EM_TRANSITO, QT_VOTOS_NOMINAIS, NM_TIPO_DESTINACAO_VOTOS,
QT_VOTOS_NOMINAIS_VALIDOS, CD_SIT_TOT_TURNO, DS_SIT_TOT_TURNO
```

Colunas de votos mais usadas: `QT_VOTOS_NOMINAIS`, `QT_VOTOS_NOMINAIS_VALIDOS`.

---

### 3.2 `votacao_partido_munzona_2026.zip` (~22 MB)

Votos de **legenda / partido** por município e zona (útil para cargos proporcionais).

Estrutura interna: `leiame.pdf` + CSVs por UF/`BR`/`BRASIL` (mesmo padrão de nomenclatura).

**38 colunas** (destaques):

```text
NR_TURNO, SG_UF, CD_MUNICIPIO, NR_ZONA, CD_CARGO, DS_CARGO,
NR_PARTIDO, SG_PARTIDO, NM_PARTIDO,
QT_VOTOS_LEGENDA_VALIDOS, QT_VOTOS_NOM_CONVR_LEG_VALIDOS,
QT_TOTAL_VOTOS_LEG_VALIDOS, QT_VOTOS_NOMINAIS_VALIDOS,
QT_VOTOS_LEGENDA_ANUL_SUBJUD, QT_VOTOS_NOMINAIS_ANUL_SUBJUD,
QT_VOTOS_LEGENDA_ANULADOS, QT_VOTOS_NOMINAIS_ANULADOS
```

---

### 3.3 `detalhe_votacao_munzona_2026.zip` (~3 MB)

Detalhe da **apuração** por município/zona (aptos, comparecimento, brancos, nulos, válidos) — sem desdobrar por candidato.

**47 colunas** (destaques):

```text
NR_TURNO, SG_UF, CD_MUNICIPIO, NR_ZONA, CD_CARGO, DS_CARGO,
QT_APTOS, QT_TOTAL_SECOES, QT_COMPARECIMENTO, QT_ABSTENCOES,
QT_TOTAL_VOTOS_VALIDOS, QT_VOTOS_NOMINAIS_VALIDOS,
QT_VOTOS_BRANCOS, QT_TOTAL_VOTOS_NULOS, QT_VOTOS_NULOS,
HH_ULTIMA_TOTALIZACAO, DT_ULTIMA_TOTALIZACAO
```

---

### 3.4 `detalhe_votacao_secao_2026.zip` (~224 MB)

Detalhe da apuração **por seção eleitoral** (granularidade mais fina que mun/zona).

```text
leiame.pdf
detalhe_votacao_secao_2026_{UF|BR}.csv   (~30 CSVs)
```

**37 colunas** (destaques):

```text
NR_TURNO, SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO, CD_CARGO, DS_CARGO,
QT_APTOS, QT_COMPARECIMENTO, QT_ABSTENCOES,
QT_VOTOS_NOMINAIS, QT_VOTOS_BRANCOS, QT_VOTOS_NULOS, QT_VOTOS_LEGENDA,
NR_LOCAL_VOTACAO, NM_LOCAL_VOTACAO, DS_LOCAL_VOTACAO_ENDERECO,
ST_SECAO_INSTALADA, ST_SECAO_ANULADA, CD_MODELO_URNA, DS_MODELO_URNA
```

---

### 3.5 `votacao_secao_2026_{UF|BR}.zip` (~2,9 GB no total)

Um ZIP **por UF** (e `BR` para Presidente). Dentro de cada um:

```text
leiame.pdf
votacao_secao_2026_{UF}.csv
```

Votos por **candidato/votável × seção**. Inclui brancos/nulos via códigos em `NR_VOTAVEL` / `NM_VOTAVEL`.

**26 colunas:**

```text
DT_GERACAO, HH_GERACAO, ANO_ELEICAO, CD_TIPO_ELEICAO, NM_TIPO_ELEICAO,
NR_TURNO, CD_ELEICAO, DS_ELEICAO, DT_ELEICAO, TP_ABRANGENCIA,
SG_UF, SG_UE, NM_UE, CD_MUNICIPIO, NM_MUNICIPIO, NR_ZONA, NR_SECAO,
CD_CARGO, DS_CARGO, NR_VOTAVEL, NM_VOTAVEL, QT_VOTOS,
NR_LOCAL_VOTACAO, SQ_CANDIDATO, NM_LOCAL_VOTACAO, DS_LOCAL_VOTACAO_ENDERECO
```

#### Tamanhos aproximados (ZIP)

| Arquivo | Tamanho |
|---------|---------|
| `votacao_secao_2026_SP.zip` | 808 MB |
| `votacao_secao_2026_RJ.zip` | 296 MB |
| `votacao_secao_2026_MG.zip` | 268 MB |
| `votacao_secao_2026_BR.zip` | 242 MB |
| `votacao_secao_2026_BA.zip` | 171 MB |
| `votacao_secao_2026_PR.zip` | 152 MB |
| `votacao_secao_2026_RS.zip` | 150 MB |
| demais UFs | 5–106 MB cada |

`votacao_secao_2026_BR.zip` = Presidente por seção (turnos 1 e 2).  
`votacao_secao_2026_{UF}.zip` = cargos daquela UF por seção.

---

### 3.6 `consulta_cand_2026.zip` (~3,1 MB)

Cadastro de candidatos (para cruzar com `SQ_CANDIDATO` / número de urna).

```text
leiame.pdf
consulta_cand_2026_{UF}.csv
consulta_cand_2026_BR.csv
consulta_cand_2026_BRASIL.csv
```

**50 colunas** (destaques):

```text
NR_TURNO, SG_UF, SG_UE, CD_CARGO, DS_CARGO,
SQ_CANDIDATO, NR_CANDIDATO, NM_CANDIDATO, NM_URNA_CANDIDATO,
NR_PARTIDO, SG_PARTIDO, NM_PARTIDO,
CD_GENERO, DS_GENERO, CD_COR_RACA, DS_COR_RACA,
CD_GRAU_INSTRUCAO, DS_GRAU_INSTRUCAO, CD_OCUPACAO, DS_OCUPACAO,
CD_SIT_TOT_TURNO, DS_SIT_TOT_TURNO
```

No arquivo `BR`: cargos `PRESIDENTE` e `VICE-PRESIDENTE`.

---

## 4. Qual arquivo usar para cada análise

| Objetivo | Arquivo recomendado |
|----------|---------------------|
| Presidente / Deputado Federal agregados por mun/zona | `votacao_candidato_munzona_2026.zip` |
| Só 1º turno | filtrar `NR_TURNO = 1` |
| Presidente por seção | `votacao_secao_2026_BR.zip` |
| Deputados por seção numa UF | `votacao_secao_2026_{UF}.zip` |
| Comparecimento / brancos / nulos | `detalhe_votacao_*` |
| Voto de legenda (proporcional) | `votacao_partido_munzona_2026.zip` |
| Nome, partido, perfil do candidato | `consulta_cand_2026.zip` |

### Exemplo rápido (pandas)

```python
import pandas as pd

df = pd.read_csv(
    "votacao_candidato_munzona_2026_SP.csv",
    sep=";",
    encoding="latin-1",
    dtype=str,
)
df_1t = df[df["NR_TURNO"] == "1"]
dep_fed = df_1t[df_1t["DS_CARGO"].str.upper() == "DEPUTADO FEDERAL"]
pres_br = pd.read_csv(
    "votacao_candidato_munzona_2026_BR.csv",
    sep=";",
    encoding="latin-1",
    dtype=str,
)
pres_1t = pres_br[
    (pres_br["NR_TURNO"] == "1")
    & (pres_br["DS_CARGO"].str.upper() == "PRESIDENTE")
]
```

---

## 5. Turnos e cargos (comportamento observado)

| Escopo | Turnos no arquivo | Cargos típicos |
|--------|-------------------|----------------|
| `*_BR.csv` / `votacao_secao_*_BR` | 1 e 2 | Presidente |
| `*_BRASIL.csv` (votacao_candidato) | 1 e 2 | Todos os cargos, consolidado nacional |
| `*_{UF}.csv` | principalmente 1; 2 se houve 2º turno de governador | Deputado Federal, Deputado Estadual, Senador, Governador |

**Diferença crítica:** `BR` ≠ `BRASIL`. Use `BR` para análise só de Presidente; use `BRASIL` ou os CSVs por UF para Deputado Federal.

Não há arquivos separados “só 1º turno” / “só 2º turno” no portal: o recorte é feito pelo campo `NR_TURNO`.

---

## 6. Metadados e links auxiliares

| Arquivo | Descrição |
|---------|-----------|
| `downloads/links_votacao_2026.csv` | Colunas: `dataset`, `name`, `filename`, `url` |
| `downloads/urls_votacao.txt` | Uma URL por linha (para re-download) |
| `downloads/resultados-2026.json` | Resposta bruta da API CKAN do dataset |
| `downloads/candidatos-2026.json` | Idem para candidatos |

API usada para listar recursos:

```text
https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026
https://dadosabertos.tse.jus.br/api/3/action/package_show?id=candidatos-2026
```

---

## 7. O que **não** foi baixado

O portal tem outros pacotes 2026 (Boletins de Urna, logs Gedai, fotos, bens, prestação de contas, etc.). Esta pasta contém apenas:

1. Votação de candidatos / partidos / detalhe (mun-zona e seção)
2. Cadastro `consulta_cand`

Se precisar de BU, fotos ou contas, baixar a partir dos datasets correspondentes em [dadosabertos.tse.jus.br](https://dadosabertos.tse.jus.br/dataset/?q=2026).

---

## 8. Licença

Dados publicados pelo TSE sob **Creative Commons Attribution** (conforme metadados do portal). Citar a fonte: Tribunal Superior Eleitoral — Portal de Dados Abertos.
