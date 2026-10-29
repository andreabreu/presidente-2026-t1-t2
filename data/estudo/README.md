# Dados do estudo (pacote enxuto)

Tabelas e JSON usados no relatório **Presidente 2026 — 1º × 2º turno**.

- **`estudo_payload.json`** — números exatos do HTML (`docs/estudo_t1_t2.html`)
- **CSVs** — placar, UF, municípios, fluxo, resíduos, apuração
- **`swing_saldos_secao.parquet`** — saldos por seção (~499 mil urnas; ~31 MB)
- **`manifest.json`** — inventário

Fonte original: [TSE Dados Abertos — Resultados 2026](https://dadosabertos.tse.jus.br/dataset/resultados-2026).

Os zips brutos **não** entram neste pacote (vários GB). Veja o README na raiz do repositório para baixá-los e regenerar o pipeline.
