# Nota jurídica / limites de interpretação (não é parecer advocatício)

## O que os dados abertos permitem
- Verificar consistência interna dos CSVs de totalização (identidades, agregações, BR vs BRASIL).
- Descrever placares, participação e padrões territoriais.
- Gerar **filas de auditoria documental** (risk_score), não juízos de ilicitude.

## O que não permitem
- Afirmar adulteração de urna, voto ou transmissão sem Boletim de Urna, log e cadeia de custódia.
- Inferir o voto de eleitor individual a partir de agregados (falácia ecológica).
- Transformar p-valor / q_fdr / risk_score em “probabilidade de fraude”.

## Referências de processo (contexto)
- Resolução TSE sobre totalização e disponibilização de BUs (ver checklist em `docs/FORENSIC_CHECKLIST.md`).
- Lei de Acesso à Informação / dados abertos: uso legítimo para auditoria cidadã estatística e documental.

## Linguagem recomendada
Usar: inconsistência documental, anomalia estatística, requer auditoria de BU.
Evitar: fraude, manipulação, urna viciada — salvo citação explícita de fonte forense independente.
