from __future__ import annotations

import json
from pathlib import Path

from tse.config import ANALYSIS_ROOT

from .components import banner, esc, paragraph, section, static_table, verbatim
from .constants import (
    ANOMALIES_EXPORT_CANDIDATES,
    ECOLOGICAL_HEADING_PREFIX,
    EXECUTIVE_VERDICTS,
    FORENSIC_CHECKLIST_PATH,
    FORENSIC_MATRIX_HEADING,
    LIMITATIONS_HEADING_PREFIX,
    MANIFEST_SOURCE,
    NOTE_PHASE_ORDER,
    REFUTATION_VERDICTS,
    VERDICT_CSS_CLASS,
)
from .context import ReportContext
from .markdown import extract_section, markdown_to_html, parse_pipe_table
from .prose import FMT_INT, FMT_TEXT

NOTES_VERBATIM_NOTE = (
    "Notas técnicas dos agentes reproduzidas na íntegra. Os números abaixo citam o source_id entre crases e não foram "
    "recalculados pelo gerador do relatório; para valores verificáveis ao clique, use as abas temáticas."
)
SUCCESS_FILE = "_SUCCESS.json"


def _notes() -> list[tuple[str, str, str]]:
    notes_dir = ANALYSIS_ROOT / "outputs" / "notes"
    found = []
    for module, title in NOTE_PHASE_ORDER:
        path = notes_dir / f"{module}.md"
        if path.exists():
            found.append((module, title, path.read_text(encoding="utf-8")))
    known = {module for module, _ in NOTE_PHASE_ORDER}
    for path in sorted(notes_dir.glob("*.md")):
        if path.stem not in known:
            found.append((path.stem, f"Nota adicional — {path.stem}", path.read_text(encoding="utf-8")))
    return found


def methods_markdown() -> str:
    parts = ["# Métodos — Eleições 2026 (concatenação das notas por fase)", ""]
    for _, title, text in _notes():
        parts += [f"## {title}", "", text.strip(), ""]
    return "\n".join(parts)


def limitations_markdown() -> str:
    parts = ["# Limitações — Eleições 2026 (por fase)", ""]
    for _, title, text in _notes():
        limitations = extract_section(text, LIMITATIONS_HEADING_PREFIX)
        ecological = extract_section(text, ECOLOGICAL_HEADING_PREFIX)
        if ecological:
            parts += [f"## {title} — declaração de falácia ecológica", "", ecological, ""]
        if limitations:
            parts += [f"## {title}", "", limitations, ""]
    return "\n".join(parts)


def methods_tab(ctx: ReportContext) -> str:
    body = "".join(f"<h3>{esc(title)}</h3>" + markdown_to_html(text) for _, title, text in _notes())
    forensic = _forensic_matrix()
    return (
        section("Matriz forense: o que é auditável com os arquivos atuais", forensic, "matriz-forense")
        + section("Apêndice metodológico (notas por fase)", verbatim(body, NOTES_VERBATIM_NOTE), "metodos")
        + section("Manifesto de execução", _manifest(ctx), "manifesto")
    )


def limitations_tab(ctx: ReportContext) -> str:
    body = markdown_to_html(limitations_markdown())
    return section("Limitações", verbatim(body, NOTES_VERBATIM_NOTE), "limitacoes")


def _forensic_matrix() -> str:
    text = (ANALYSIS_ROOT / FORENSIC_CHECKLIST_PATH).read_text(encoding="utf-8")
    block = extract_section(text, FORENSIC_MATRIX_HEADING)
    lines = [line for line in block.splitlines() if line.strip().startswith("|")]
    header, rows = parse_pipe_table(lines)
    from .markdown import inline

    rendered = [[inline(cell) for cell in row] for row in rows]
    legend = paragraph("Legenda: A = auditável com arquivos atuais · P = parcialmente (só descritivo/estatístico) · N = exige fonte adicional.")
    return legend + static_table([inline(cell) for cell in header], rendered)


def _manifest(ctx: ReportContext) -> str:
    q = ctx.queries
    manifest_path = ANALYSIS_ROOT / MANIFEST_SOURCE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    libs = manifest.get("libraries", {})
    lib_rows = [[esc(name), esc(version)] for name, version in libs.items()]
    inputs = manifest.get("inputs", [])
    input_rows = [[esc(item["path"]), esc(f"{item['bytes']:,}".replace(",", ".")), f"<code>{esc(item['sha256'])}</code>"] for item in inputs]
    success_rows = _success_rows()
    generated = q.literal_span("Q_MANIFEST_generated_at", MANIFEST_SOURCE, "generated_at", manifest.get("generated_at", ""), FMT_TEXT)
    python_version = q.literal_span("Q_MANIFEST_python", MANIFEST_SOURCE, "python", manifest.get("python", ""), FMT_TEXT)
    seed = q.literal_span("Q_MANIFEST_seed", MANIFEST_SOURCE, "seed", manifest.get("seed"), FMT_INT)
    n_inputs = q.literal_span("Q_MANIFEST_n_inputs", MANIFEST_SOURCE, "inputs", len(inputs), FMT_INT)
    total_rows = sum(row[2] for row in success_rows)
    n_rows_span = q.literal_span("Q_INGEST_total_rows", "data/interim/*/scope=*/_SUCCESS.json", "rows", total_rows, FMT_INT)
    return (
        paragraph(f"Manifesto gerado em {generated}; Python {python_version}; seed {seed}; {n_inputs} arquivos de entrada com hash SHA-256; {n_rows_span} linhas convertidas para Parquet.")
        + "<h3>Bibliotecas</h3>"
        + static_table(["biblioteca", "versão"], lib_rows)
        + "<h3>Entradas (ZIP) e hashes</h3>"
        + static_table(["arquivo", "bytes", "sha256"], input_rows)
        + "<h3>Conversão para Parquet (_SUCCESS.json)</h3>"
        + static_table(["dataset", "escopo", "linhas", "zip sha256"], [[esc(d), esc(s), esc(f"{r:,}".replace(",", ".")), f"<code>{esc(h)}</code>"] for d, s, r, h in success_rows])
    )


def _success_rows() -> list[tuple[str, str, int, str]]:
    rows = []
    for path in sorted((ANALYSIS_ROOT / "data" / "interim").glob(f"*/scope=*/{SUCCESS_FILE}")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.append((payload.get("dataset", path.parts[-3]), payload.get("scope", path.parts[-2]), int(payload.get("rows", 0)), payload.get("zip_sha256", "")))
    return rows


def hypotheses_tab(ctx: ReportContext) -> str:
    q = ctx.queries
    counts = " · ".join(
        f"{status}: {q.hypotheses_count_span(f'Q_HYP_count_{status}', {'status': status})}" for status in ("proposed", "computed", "reviewed", "published")
    )
    rows = []
    for item in ctx.hypotheses:
        verdict = item.get("verdict") or ""
        css = VERDICT_CSS_CLASS.get(verdict, "")
        rows.append(
            [
                esc(item["id"]),
                esc(item["title"]),
                esc(item.get("class", "")),
                esc(item.get("unit", "")),
                esc(item.get("null_hypothesis", "")),
                esc(item.get("status", "")),
                f'<span class="badge {css}">{esc(verdict)}</span>' if verdict else "—",
            ]
        )
    return section(
        "Hipóteses registradas",
        paragraph(f"Lista integral de <code>hypotheses.yaml</code>. Contagens por status — {counts}.")
        + static_table(["id", "título", "classe", "unidade", "hipótese nula", "status", "veredito"], rows),
        "hipoteses",
    )


def results_hypotheses_table(ctx: ReportContext) -> str:
    rows = []
    for item in ctx.hypotheses:
        if item.get("status") == "proposed" or item.get("verdict") in REFUTATION_VERDICTS:
            continue
        verdict = item.get("verdict")
        label = f'<span class="badge {VERDICT_CSS_CLASS[verdict]}">{esc(verdict)}</span>' if verdict in EXECUTIVE_VERDICTS else '<span class="badge verdict-pendente">não revisado</span>'
        tables = " ".join(f"<code>{esc(t.strip())}</code>" for t in str(item.get("table", "")).split(","))
        rows.append([esc(item["id"]), esc(item["title"]), esc(item.get("class", "")), esc(item.get("status", "")), label, tables, esc(item.get("notes", "")) if verdict else ""])
    return section(
        "Hipóteses calculadas e status de revisão",
        paragraph("Itens calculados aparecem com o veredito do Revisor quando houver; sem veredito ficam marcados como não revisados. Refutados e inconclusivos estão na aba Revisão.")
        + static_table(["id", "título", "classe", "status", "veredito", "tabelas", "ressalvas"], rows),
        "hipoteses-calculadas",
    )


def raw_data_tab(ctx: ReportContext) -> str:
    store = ctx.store
    rows = []
    for source_id in store.available_ids():
        meta = store.meta(source_id)
        embedded = source_id in store.specs
        rows.append(
            [
                f"<code>{esc(source_id)}</code>",
                esc(meta.get("title_pt", "")),
                esc(meta.get("unit", "")),
                esc(f"{meta.get('n_rows', 0):,}".replace(",", ".")),
                esc(", ".join(meta.get("hypothesis_ids", []))),
                esc(meta.get("script", "")),
                "embutida" if embedded else "só arquivo",
                f'<a href="{esc(store.csv_relative_path(source_id))}">csv</a> · <a href="outputs/tables/{esc(source_id)}.parquet">parquet</a> · <a href="outputs/tables/{esc(source_id)}.meta.json">meta</a>',
            ]
        )
    export_link = _anomalies_export_link()
    figures = sorted(path.name for path in (ANALYSIS_ROOT / "outputs" / "figures").glob("*.json"))
    figure_list = "<ul>" + "".join(f'<li><a href="outputs/figures/{esc(name)}">{esc(name)}</a></li>' for name in figures) + "</ul>"
    return section(
        "Dados brutos: tabelas, figuras e exportações",
        paragraph("Todas as tabelas geradas por script. Tabelas marcadas como embutidas podem ser filtradas e exportadas nas abas; as demais estão disponíveis apenas como arquivo.")
        + export_link
        + static_table(["source_id", "título", "unidade", "linhas", "hipóteses", "script", "no relatório", "arquivos"], rows)
        + "<h3>Figuras (plotly JSON)</h3>"
        + figure_list
        + "<h3>Documentos gerados</h3>"
        + '<ul><li><a href="outputs/METHODS.md">outputs/METHODS.md</a></li><li><a href="outputs/LIMITATIONS.md">outputs/LIMITATIONS.md</a></li><li><a href="outputs/tables/queries.yaml">outputs/tables/queries.yaml</a> (registro de consultas dos números em prosa)</li><li><a href="outputs/run_manifest.json">outputs/run_manifest.json</a></li></ul>',
        "dados",
    )


def _anomalies_export_link() -> str:
    for candidate in ANOMALIES_EXPORT_CANDIDATES:
        if (ANALYSIS_ROOT / candidate).exists():
            return paragraph(f'Exportação JSON das anomalias para auditoria externa: <a href="{esc(candidate)}">{esc(candidate)}</a>.')
    return banner("Exportação JSON das anomalias ainda não gerada.", "warn")


def write_markdown_outputs(outputs_dir: Path) -> tuple[Path, Path]:
    methods = outputs_dir / "METHODS.md"
    limitations = outputs_dir / "LIMITATIONS.md"
    methods.write_text(methods_markdown(), encoding="utf-8")
    limitations.write_text(limitations_markdown(), encoding="utf-8")
    return methods, limitations
