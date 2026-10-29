# Presidente 2026 — estudo 1º × 2º turno

Análise dos **dados abertos do TSE** sobre a eleição presidencial de 2026: placar, aritmética da virada, transferência de votos (estimativa ecológica), abstenções retomadas, urnas com voto concentrado e linha do tempo da apuração.

## Ver online (GitHub Pages)

- **Início:** https://andreabreu.github.io/presidente-2026-t1-t2/
- **Estudo completo:** https://andreabreu.github.io/presidente-2026-t1-t2/estudo_t1_t2.html
- **Repositório:** https://github.com/andreabreu/presidente-2026-t1-t2

Se o Pages ainda não estiver ativo: **Settings → Pages → Deploy from a branch** → `main` → pasta **`/docs`**.

A pasta [`docs/`](docs/) contém o HTML estático do estudo (Plotly embutido; funciona offline).

## Abrir localmente

```bash
# relatório gerado
open docs/estudo_t1_t2.html
# ou
open analysis/outputs/estudo_t1_t2.html
```

Servidor opcional (se já estiver rodando na porta 8765):

- [http://127.0.0.1:8765/estudo_t1_t2.html](http://127.0.0.1:8765/estudo_t1_t2.html)

## Regenerar o estudo

A partir de `analysis/` (com o ambiente e as tabelas do pipeline prontas):

```bash
cd analysis
.venv/bin/python -m tse.report.estudo
```

Isso atualiza:

- `analysis/outputs/estudo_t1_t2.html`
- `docs/estudo_t1_t2.html` (GitHub Pages)

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

## Fonte dos dados

[TSE — Dados Abertos](https://dadosabertos.tse.jus.br/): votação por seção, detalhe da votação, município/zona e boletins de urna.

## Limites

- Transferências entre grupos do 1º turno são **estimativas agregadas** (inferência ecológica), não o voto de pessoas.
- Os totais públicos permitem fechar a aritmética nacional e municipal; a conferência documental (BU impresso e registros das urnas) continua sendo o passo definitivo quando houver dúvida pontual.
- Estatística descreve padrões e raridades; não substitui auditoria documental.

## Estrutura do repositório

```
docs/                 # site do GitHub Pages
  index.html          # página inicial
  estudo_t1_t2.html   # estudo interativo
analysis/             # pipeline e geração do HTML
  src/tse/report/estudo.py
  outputs/            # cópia local do estudo
```

## Licença dos dados

Os microdados eleitorais são públicos, divulgados pelo TSE. Este estudo é uma análise independente; não é material oficial do Tribunal.
