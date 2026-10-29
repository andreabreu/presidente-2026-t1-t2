# Fechamento do pipeline (pós-Claude)

## Entregue agora
- `outputs/report.html` (~41 MB) — abas Executivo→Dados, tabelas filtráveis
- `outputs/tables/rev_vereditos.csv` + `rev_reproducao.csv`
- `hypotheses.yaml` — 30 hipóteses `reviewed` (14 SUSTENTADO, 13 FRÁGIL, 2 REFUTADO, 1 INCONCLUSIVO)
- Investigação: `investigation/timeline/`, `legal/limites.md`, `evidence_matrix.csv`, `sources/README.md`
- `outputs/METHODS.md`, `LIMITATIONS.md`
- Testes: **75 passed**

## Como abrir
```bash
open /Users/andreabreu/Developer/TSE/analysis/outputs/report.html
# ou
cd analysis && .venv/bin/python -m tse.report
```

## Melhorias prioritárias (próximo ciclo)
1. **Re-rodar anomalias** com hooks `val_inconsistencias` + `swing_residuos_flag` (notas dizem componentes zerados na 1ª passagem).
2. **Baixar BUs** só das top-N seções severity≥3 sem flag de exclusão (fila forense real).
3. **Baseline 2018/2022** presidente (já em `downloads/`) — mesma seção/município, delta de comparecimento e share.
4. **Enxugar report.html** (lazy-load JSON por aba; hoje embute muitas tabelas → 41 MB).
5. **Corrigir lint de dígitos** no gerador (notas verbatim / títulos com anos) ou marcar blocos `data-lint=exempt`.
6. **Crosswalk IBGE oficial** (substituir o de 2018 citado nas limitações).
7. **EI / bootstrap espacial** nas viradas (intervalos mais honestos que Goodman pontual).
8. Comparar fingerprint Klimek 2022×2026 por UF.
