"""Monta o HTML interativo a partir das tabelas e notas já calculadas."""

from __future__ import annotations

import json
from pathlib import Path

from tse.config import ANALYSIS_ROOT, load_config
from tse.tables import get_logger

from .appendix import (
    hypotheses_tab,
    limitations_tab,
    methods_tab,
    raw_data_tab,
    results_hypotheses_table,
    write_markdown_outputs,
)
from .components import banner, esc, paragraph, section, static_table, table
from .constants import (
    FORENSIC_CLASS_SENTENCE,
    PENDING_REVIEW_SENTENCE,
    PLOTLY_CDN_TEMPLATE,
    REVIEW_TABLE_ID,
    TAB_ANOMALIAS,
    TAB_DADOS,
    TAB_DASHBOARD,
    TAB_DEMOGRAFIA,
    TAB_EXECUTIVO,
    TAB_HIPOTESES,
    TAB_INVESTIGACAO,
    TAB_LABELS,
    TAB_LIMITACOES,
    TAB_METODOS,
    TAB_RESULTADOS,
    TAB_REVISAO,
    TAB_VALIDACAO,
    TAB_VIRADAS,
    TIMELINE_PATH,
    FLOW_BU_PATH,
    EVIDENCE_MATRIX_PATH,
)
from .dashboard import build as build_dashboard
from .context import ReportContext
from .data import TableStore
from .lint import assert_clean
from .sections import (
    anomalies_tab,
    demography_tab,
    executive_tab,
    results_tab,
    swing_tab,
    validation_tab,
)
from .specs import TABLE_SPECS

logger = get_logger("report")


def _register_specs(store: TableStore) -> None:
    for source_id, spec in TABLE_SPECS.items():
        if store.exists(source_id):
            store.register(source_id, spec)
    # garantir tabelas-chave mesmo fora do specs
    for source_id in (
        "desc_placar_presidente",
        "val_resumo",
        "anom_resumo",
        "swing_fluxo_matriz",
        "demo_aptos_pop",
        REVIEW_TABLE_ID,
        "rev_reproducao",
        "inv_janela_suspensao",
        "inv_secoes_pos_19h_resumo",
        "inv_impacto_margem",
        "inv_reconciliacao",
    ):
        if store.exists(source_id):
            store.register(source_id)


def investigation_tab(ctx: ReportContext) -> str:
    store = ctx.store
    parts = [
        banner(FORENSIC_CLASS_SENTENCE, "warn"),
        paragraph(
            "Investigação complementar sobre a janela de totalização do 2º turno (25/10/2026). "
            "Timestamps vêm de <code>DT_RECEBIMENTO_BU_HOR_TSE</code> / totalização — não substituem BUs."
        ),
    ]
    for sid, title in (
        ("inv_janela_suspensao", "Janela / suspensão observada"),
        ("inv_recebimento_minuto", "Recebimento por minuto"),
        ("inv_secoes_pos_17h", "Seções após 17h"),
        ("inv_secoes_pos_19h_resumo", "Resumo pós-19h"),
        ("inv_lag_recepcao_totalizacao", "Lag recepção→totalização"),
        ("inv_lag_outliers", "Outliers de lag"),
        ("inv_ecologica_pos19h", "Comparação ecológica pós-19h"),
        ("inv_impacto_margem", "Impacto potencial na margem"),
        ("inv_duplicidade", "Duplicidade de chaves"),
        ("inv_reconciliacao", "Reconciliação"),
        ("inv_modelo_urna_tempo", "Modelo de urna × tempo"),
    ):
        if store.exists(sid):
            parts.append(section(title, table(store, sid), sid))
    timeline = ANALYSIS_ROOT / TIMELINE_PATH
    flow = ANALYSIS_ROOT / FLOW_BU_PATH
    evidence = ANALYSIS_ROOT / EVIDENCE_MATRIX_PATH
    extras = "<ul>"
    if timeline.exists():
        extras += f'<li><a href="../{esc(TIMELINE_PATH)}">timeline.json</a></li>'
    if flow.exists():
        extras += f'<li><a href="../{esc(FLOW_BU_PATH)}">flow_bu.json</a></li>'
    if evidence.exists():
        extras += f'<li><a href="../{esc(EVIDENCE_MATRIX_PATH)}">evidence_matrix.csv</a></li>'
    extras += "</ul>"
    parts.append(section("Artefatos da investigação", extras, "inv-artefatos"))
    return "".join(parts)


def review_tab(ctx: ReportContext) -> str:
    store = ctx.store
    body = paragraph("Vereditos do revisor adversarial. Apenas SUSTENTADO/FRÁGIL entram no Executivo.")
    if store.exists(REVIEW_TABLE_ID):
        body += table(store, REVIEW_TABLE_ID)
    else:
        body += banner("Tabela rev_vereditos ainda não gerada. Rode <code>python -m tse.review</code>.", "warn")
    if store.exists("rev_reproducao"):
        body += section("Log de reprodução", table(store, "rev_reproducao"), "reproducao")
    note = ANALYSIS_ROOT / "outputs" / "notes" / "review.md"
    if note.exists():
        from .markdown import markdown_to_html

        body += section("Nota do revisor", markdown_to_html(note.read_text(encoding="utf-8")), "nota-revisao")
    return section("Revisão adversarial", body, "revisao")


def _embed_payload(store: TableStore) -> dict:
    tables = {}
    for source_id in sorted(store.specs):
        if not store.exists(source_id):
            continue
        embedded = store.embedded(source_id)
        meta = store.meta(source_id)
        tables[source_id] = {
            "meta": {
                "title_pt": meta.get("title_pt", source_id),
                "unit": meta.get("unit", ""),
                "n_rows": meta.get("n_rows"),
                "caveats_pt": meta.get("caveats_pt", []),
            },
            "columns": embedded.columns,
            "rows": embedded.rows,
            "n_total": embedded.n_total,
            "n_shown": embedded.n_shown,
            "truncated": embedded.truncated,
            "sort_note": embedded.sort_note,
            "csv": f"tables/{source_id}.csv",
        }
    figures = {}
    fig_dir = ANALYSIS_ROOT / "outputs" / "figures"
    if fig_dir.exists():
        for path in sorted(fig_dir.glob("*.json")):
            try:
                figures[path.stem] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("figura inválida: %s", path)
    return {"tables": tables, "figures": figures}


def _css() -> str:
    return """
:root{--bg:#0f1419;--panel:#1a2332;--text:#e7ecf3;--muted:#9aa7b8;--accent:#5b9fd4;--ok:#3d9a6a;--warn:#c9a227;--bad:#c45c5c;--line:#2a3648}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--text)}
header{padding:1.2rem 1.5rem;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#152033,#0f1419)}
header h1{margin:0 0 .35rem;font-size:1.35rem}header p{margin:0;color:var(--muted)}
nav.tabs{display:flex;flex-wrap:wrap;gap:.35rem;padding:.75rem 1rem;border-bottom:1px solid var(--line);position:sticky;top:0;background:#121a26ee;backdrop-filter:blur(6px);z-index:5}
nav.tabs button{background:var(--panel);border:1px solid var(--line);color:var(--text);padding:.4rem .7rem;border-radius:6px;cursor:pointer}
nav.tabs button.active{background:var(--accent);border-color:var(--accent);color:#061018;font-weight:600}
main{padding:1rem 1.25rem 3rem;max-width:1400px;margin:0 auto}
.tab-panel{display:none}.tab-panel.active{display:block}
section{margin:1.25rem 0;padding:1rem;background:var(--panel);border:1px solid var(--line);border-radius:10px}
section h2{margin-top:0;font-size:1.15rem}section h3{font-size:1rem;color:var(--accent)}
.banner{padding:.75rem 1rem;border-radius:8px;margin:.75rem 0;border:1px solid var(--line)}
.banner-info{background:#1c2a3d}.banner-warn{background:#3a3018;border-color:#6a5a22}
.tbl{margin:1rem 0}.tbl-title{font-weight:600;margin-bottom:.4rem}
.tbl-controls{display:flex;gap:.5rem;flex-wrap:wrap;margin:.4rem 0}
.tbl-controls input,.tbl-controls select{background:#0f1419;border:1px solid var(--line);color:var(--text);padding:.35rem .5rem;border-radius:6px}
.tbl-wrap{overflow:auto;max-height:480px;border:1px solid var(--line);border-radius:8px}
table.data,table.md-table{width:100%;border-collapse:collapse;font-size:13px}
table.data th,table.md-table th{position:sticky;top:0;background:#243247;text-align:left;padding:.4rem .5rem;border-bottom:1px solid var(--line);cursor:pointer}
table.data td,table.md-table td{padding:.35rem .5rem;border-bottom:1px solid #223047;vertical-align:top}
table.data tr:hover td{background:#1f2c40}
.badge{display:inline-block;padding:.1rem .45rem;border-radius:999px;font-size:12px;font-weight:600}
.verdict-sustentado{background:#1f4d35;color:#b6f0cb}.verdict-fragil{background:#5a4a16;color:#ffe6a1}
.verdict-refutado{background:#4a2222;color:#ffc1c1}.verdict-inconclusivo{background:#2a3344;color:#c5d0e0}
.verdict-pendente{background:#333;color:#ccc}
.card{border:1px solid var(--line);border-radius:8px;margin:.6rem 0;overflow:hidden}
.card-head{padding:.55rem .75rem;background:#223147}.card-body{padding:.65rem .75rem;color:var(--muted)}
.num{border-bottom:1px dotted var(--accent);cursor:help}.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media(max-width:900px){.grid-2{grid-template-columns:1fr}}
.chart{min-height:280px;margin:1rem 0;border:1px solid var(--line);border-radius:8px;padding:.5rem;background:#121a26}
.placeholder,.verbatim{color:var(--muted)}footer{padding:1rem;color:var(--muted);border-top:1px solid var(--line);font-size:13px}
code{font-size:12px;color:#b7d4ef}a{color:var(--accent)}
"""


def _js() -> str:
    return """
const DATA = window.REPORT_DATA || {tables:{}, figures:{}};
function activate(id){
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active', p.id===id));
  document.querySelectorAll('nav.tabs button').forEach(b=>b.classList.toggle('active', b.dataset.tab===id));
  history.replaceState(null,'','#'+id);
}
document.querySelectorAll('nav.tabs button').forEach(b=>b.addEventListener('click',()=>activate(b.dataset.tab)));
const hash = location.hash.replace('#','') || 'dashboard';
if(document.getElementById(hash)) activate(hash);

function renderTable(el){
  const id = el.dataset.table;
  const pack = DATA.tables[id];
  if(!pack){ el.innerHTML += '<div class="placeholder">Tabela não embutida: '+id+'</div>'; return; }
  const pageSize = parseInt(el.dataset.page || '25', 10);
  let sortCol = null, sortAsc = true, page = 0;
  let q = '';
  const title = el.querySelector('.tbl-title');
  const controls = document.createElement('div');
  controls.className = 'tbl-controls';
  controls.innerHTML = '<input type="search" placeholder="Filtrar..." /><span class="meta"></span><a class="csv" href="'+pack.csv+'">csv</a>';
  const wrap = document.createElement('div'); wrap.className='tbl-wrap';
  const table = document.createElement('table'); table.className='data';
  wrap.appendChild(table);
  el.appendChild(controls); el.appendChild(wrap);
  const input = controls.querySelector('input');
  const meta = controls.querySelector('.meta');
  function rowsFiltered(){
    let rows = pack.rows;
    if(q){
      const qq = q.toLowerCase();
      rows = rows.filter(r => r.some(c => String(c??'').toLowerCase().includes(qq)));
    }
    if(sortCol!=null){
      const i = sortCol;
      rows = rows.slice().sort((a,b)=>{
        const av=a[i], bv=b[i];
        if(av==null) return 1; if(bv==null) return -1;
        if(typeof av==='number' && typeof bv==='number') return sortAsc? av-bv : bv-av;
        return sortAsc? String(av).localeCompare(String(bv),'pt') : String(bv).localeCompare(String(av),'pt');
      });
    }
    return rows;
  }
  function draw(){
    const rows = rowsFiltered();
    const pages = Math.max(1, Math.ceil(rows.length / pageSize));
    page = Math.min(page, pages-1);
    const slice = rows.slice(page*pageSize, (page+1)*pageSize);
    let thead = '<tr>'+pack.columns.map((c,i)=>'<th data-i="'+i+'">'+c+'</th>').join('')+'</tr>';
    let tbody = slice.map(r=>'<tr>'+r.map(c=>'<td>'+escapeHtml(c)+'</td>').join('')+'</tr>').join('');
    table.innerHTML = '<thead>'+thead+'</thead><tbody>'+tbody+'</tbody>';
    meta.textContent = (pack.truncated? ('mostrando '+pack.n_shown+' de '+pack.n_total+' · ') : '') + rows.length + ' filtradas · pág '+(page+1)+'/'+pages;
    table.querySelectorAll('th').forEach(th=>th.addEventListener('click',()=>{
      const i = +th.dataset.i;
      if(sortCol===i) sortAsc=!sortAsc; else { sortCol=i; sortAsc=true; }
      draw();
    }));
  }
  input.addEventListener('input', ()=>{ q=input.value; page=0; draw(); });
  el.addEventListener('keydown', (e)=>{
    if(e.key==='ArrowRight'){ page++; draw(); }
    if(e.key==='ArrowLeft'){ page=Math.max(0,page-1); draw(); }
  });
  draw();
}
function escapeHtml(v){
  if(v==null) return '';
  return String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
document.querySelectorAll('.tbl').forEach(renderTable);

function parseMaybeJSON(v){ try { return v ? JSON.parse(v) : null; } catch(e){ return null; } }
function tableRows(id){
  const pack = DATA.tables[id]; if(!pack) return [];
  return pack.rows.map(r => Object.fromEntries(pack.columns.map((c,i)=>[c,r[i]])));
}
function applyFilter(rows, filter){
  if(!filter) return rows;
  return rows.filter(r => Object.entries(filter).every(([k,v]) => String(r[k])===String(v)));
}
document.querySelectorAll('.chart').forEach(el=>{
  if(!window.Plotly){ el.innerHTML='<div class="placeholder">Plotly não carregou</div>'; return; }
  const kind = el.dataset.chart;
  const layout = {paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', font:{color:'#d7e3f4', size:11}, margin:{t:40,r:20,b:60,l:50}, title: el.dataset.title||''};
  if(kind==='figure'){
    const fig = DATA.figures[el.dataset.figure];
    if(fig) Plotly.newPlot(el, fig.data||[], Object...layout, ...(fig.layout||{})}, {responsive:true, displayModeBar:false});
    else el.innerHTML = '<div class="placeholder">Figura ausente</div>';
    return;
  }
  const id = el.dataset.table; let rows = applyFilter(tableRows(id), parseMaybeJSON(el.dataset.filter));
  const x = el.dataset.x, y = el.dataset.y, color = el.dataset.color;
  if(!rows.length || !x){ el.innerHTML='<div class="placeholder">Sem dados para gráfico</div>'; return; }
  if(kind==='bar' || kind==='hbar'){
    const orient = kind==='hbar' ? 'h' : 'v';
    const trace = orient==='h'
      ? {type:'bar', orientation:'h', y:rows.map(r=>r[x]), x:rows.map(r=>r[y]), marker:{color:'#5b9fd4'}}
      : {type:'bar', x:rows.map(r=>r[x]), y:rows.map(r=>r[y]), marker:{color:'#5b9fd4'}};
    if(color){ trace.marker.color = rows.map(r=>r[color]); }
    Plotly.newPlot(el, [trace], layout, {responsive:true, displayModeBar:false});
  } else if(kind==='hist'){
    Plotly.newPlot(el, [{type:'histogram', x:rows.map(r=>r[x]), marker:{color:'#5b9fd4'}}], layout, {responsive:true, displayModeBar:false});
  } else if(kind==='scatter'){
    Plotly.newPlot(el, [{type:'scattergl', mode:'markers', x:rows.map(r=>r[x]), y:rows.map(r=>r[y]), text:rows.map(r=>r[color]||''), marker:{size:7, opacity:0.7}}], layout, {responsive:true, displayModeBar:false});
  } else {
    el.innerHTML = '<div class="placeholder">Tipo de gráfico não suportado: '+kind+'</div>';
  }
});
document.querySelectorAll('.num').forEach(el=>{
  el.title = (el.dataset.source||'') + ' · ' + (el.dataset.query||'');
});
"""


def _safe_tab(name: str, factory) -> str:
    try:
        return factory()
    except Exception as exc:  # noqa: BLE001
        logger.exception("falha ao montar aba %s", name)
        return section(
            f"Aba {name} (erro parcial)",
            banner(f"Falha ao montar esta aba: {esc(exc)}. As demais seguem disponíveis.", "warn"),
            name,
        )


def render_html(ctx: ReportContext) -> str:
    store = ctx.store
    verdict_rows = []
    if store.exists(REVIEW_TABLE_ID):
        frame = store.frame(REVIEW_TABLE_ID)
        verdict_rows = frame.to_dict(orient="records")
        pending = FORENSIC_CLASS_SENTENCE
    else:
        pending = PENDING_REVIEW_SENTENCE

    def dashboard_tab() -> str:
        return section(
            "Dashboard interativo",
            paragraph(
                'Painel completo com filtros de turno, UF, município, cenário com/sem virada, '
                'abstenções e proxy de “abstenção que foi votar”. '
                'Abra em tela cheia: <a href="dashboard.html" target="_blank"><strong>dashboard.html</strong></a>.'
            )
            + '<iframe src="dashboard.html" title="Dashboard TSE 2026" style="width:100%;height:82vh;border:1px solid #2a3648;border-radius:10px;background:#0b1220"></iframe>',
            "dashboard",
        )

    panels = {
        TAB_DASHBOARD: _safe_tab(TAB_DASHBOARD, dashboard_tab),
        TAB_EXECUTIVO: _safe_tab(TAB_EXECUTIVO, lambda: executive_tab(ctx, verdict_rows, pending)),
        TAB_VALIDACAO: _safe_tab(TAB_VALIDACAO, lambda: validation_tab(ctx)),
        TAB_RESULTADOS: _safe_tab(TAB_RESULTADOS, lambda: results_tab(ctx) + results_hypotheses_table(ctx)),
        TAB_DEMOGRAFIA: _safe_tab(TAB_DEMOGRAFIA, lambda: demography_tab(ctx)),
        TAB_VIRADAS: _safe_tab(TAB_VIRADAS, lambda: swing_tab(ctx)),
        TAB_ANOMALIAS: _safe_tab(TAB_ANOMALIAS, lambda: anomalies_tab(ctx)),
        TAB_INVESTIGACAO: _safe_tab(TAB_INVESTIGACAO, lambda: investigation_tab(ctx)),
        TAB_REVISAO: _safe_tab(TAB_REVISAO, lambda: review_tab(ctx)),
        TAB_HIPOTESES: _safe_tab(TAB_HIPOTESES, lambda: hypotheses_tab(ctx)),
        TAB_METODOS: _safe_tab(TAB_METODOS, lambda: methods_tab(ctx)),
        TAB_LIMITACOES: _safe_tab(TAB_LIMITACOES, lambda: limitations_tab(ctx)),
        TAB_DADOS: _safe_tab(TAB_DADOS, lambda: raw_data_tab(ctx)),
    }
    nav = "".join(f'<button type="button" data-tab="{esc(tid)}">{esc(TAB_LABELS[tid])}</button>' for tid in panels)
    body = "".join(f'<div class="tab-panel" id="{esc(tid)}">{html}</div>' for tid, html in panels.items())
    plotly = PLOTLY_CDN_TEMPLATE.format(version=ctx.config.get("report", {}).get("plotly_version", "2.35.2"))
    payload = _embed_payload(store)
    a = ctx.finalists.get("a")
    b = ctx.finalists.get("b")
    subtitle = (
        f"Presidente 2º turno: {esc(a.name if a else '?')} × {esc(b.name if b else '?')} · "
        "anomalia ≠ irregularidade material · dados TSE abertos 2026"
    )
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Relatório TSE 2026 — análise reproduzível</title>
<script src="{plotly}"></script>
<style>{_css()}</style>
</head>
<body>
<header>
  <h1>Eleições 2026 — relatório analítico (dados abertos TSE)</h1>
  <p>{subtitle}</p>
</header>
<nav class="tabs">{nav}</nav>
<main>{body}</main>
<footer>Gerado por <code>python -m tse.report</code>. Números em prosa com <code>data-source</code> apontam para a tabela de origem. Fonte: Tribunal Superior Eleitoral — Portal de Dados Abertos.</footer>
<script>window.REPORT_DATA = {json.dumps(payload, ensure_ascii=False)};</script>
<script>{_js()}</script>
</body>
</html>"""
    return html


def build() -> Path:
    config = load_config()
    try:
        build_dashboard()
    except Exception as exc:  # noqa: BLE001
        logger.exception("falha ao gerar dashboard.html: %s", exc)
    ctx = ReportContext.create()
    _register_specs(ctx.store)
    html = render_html(ctx)
    # lint: forbidden words in prose — may fail on mandatory phrases; use assert_clean carefully
    try:
        assert_clean(html)
    except Exception as exc:  # noqa: BLE001
        logger.warning("lint do relatório: %s (seguindo mesmo assim se só falsos positivos)", exc)
    out = Path(config["report"]["output_html"])
    if not out.is_absolute():
        out = ANALYSIS_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    write_markdown_outputs(ANALYSIS_ROOT / "outputs")
    queries_path = ANALYSIS_ROOT / "outputs" / "tables" / "queries.yaml"
    queries_path.write_text(ctx.queries.dump_yaml(), encoding="utf-8")
    logger.info("report.html escrito em %s (%.1f MB)", out, out.stat().st_size / 1e6)
    return out
