/* global Plotly */
(function () {
  "use strict";
  const D = window.ESTUDO;
  if (!D || !window.Plotly) {
    document.body.insertAdjacentHTML(
      "afterbegin",
      '<div style="padding:1rem;background:#5a1e1e;color:#fff">Falha ao carregar Plotly ou dados do estudo.</div>'
    );
    return;
  }

  const C = { lula: "#e35d6a", flavio: "#4d8dff", ok: "#3ecf8e", warn: "#f0b429", bn: "#9aa5b8", abs: "#8b6cff", elim: "#c58bff" };
  const nf0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const nf2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const nf3 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  const int = (v) => (v == null ? "—" : nf0.format(v));
  const pct = (v, d) => (v == null ? "—" : (d === 2 ? nf2 : nf1).format(v * 100) + "%");
  const mi = (v) => (v == null ? "—" : nf2.format(v / 1e6) + " milhões");
  const hhmm = (s) => (s ? String(s).slice(11, 16) : "—");
  const ts = (s) => (s ? String(s).replace(" ", "T") : s);
  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  function get(path) {
    return path.split(".").reduce((o, k) => (o == null ? o : o[k]), D);
  }
  const FORMATS = {
    raw: (v) => v,
    int: int,
    absint: (v) => int(Math.abs(v)),
    pct: (v) => pct(v),
    mi: mi,
    pp1: (v) => nf1.format(v),
    pp3: (v) => nf3.format(v),
    hhmm: hhmm,
  };
  document.querySelectorAll("[data-v]").forEach((el) => {
    const f = FORMATS[el.dataset.f || "raw"] || FORMATS.raw;
    el.textContent = f(get(el.dataset.v));
  });

  const N = D.nacional;
  document.getElementById("kRetornoPct").textContent =
    "≥ " + pct(N.retornos_min_secao / N.turnout.t1.QT_ABSTENCOES);
  document.getElementById("kQuartis").textContent = D.tempo.quartis
    .map((q) => q.grupo + ": " + nf2.format(q.residuo_pp) + " p.p.")
    .join(" · ");

  const base = {
    paper_bgcolor: "#131f33",
    plot_bgcolor: "#131f33",
    font: { color: "#dbe5f3", size: 12 },
    margin: { t: 30, r: 18, b: 50, l: 60 },
    legend: { orientation: "h", y: 1.14, x: 0 },
    xaxis: { gridcolor: "#22324b", zerolinecolor: "#3a4d6b" },
    yaxis: { gridcolor: "#22324b", zerolinecolor: "#3a4d6b" },
    separators: ",.",
    hoverlabel: { bgcolor: "#0d1728" },
  };
  const cfg = { responsive: true, displayModeBar: false };
  const charts = [];
  function L(extra) {
    const out = Object.assign({}, base, extra || {});
    out.xaxis = Object.assign({}, base.xaxis, (extra && extra.xaxis) || {});
    out.yaxis = Object.assign({}, base.yaxis, (extra && extra.yaxis) || {});
    return out;
  }
  function plot(id, data, layout) {
    const el = document.getElementById(id);
    if (!el) return;
    Plotly.newPlot(el, data, L(layout), cfg);
    charts.push(el);
  }

  function table(id, cols, rows) {
    const el = document.getElementById(id);
    if (!el) return;
    let h = "<table><thead><tr>" + cols.map((c) => '<th class="' + (c.l ? "l" : "") + '">' + c.t + "</th>").join("") + "</tr></thead><tbody>";
    rows.forEach((r) => {
      h += "<tr>" + cols.map((c) => '<td class="' + (c.l ? "l" : "") + '">' + c.f(r) + "</td>").join("") + "</tr>";
    });
    el.innerHTML = h + "</tbody></table>";
  }

  /* 1. Placar */
  const t1 = D.nacional.placar.filter((r) => r.NR_TURNO === 1).sort((a, b) => b.votos - a.votos);
  const t2 = D.nacional.placar.filter((r) => r.NR_TURNO === 2);
  const corCand = (nr) => (nr === 13 ? C.lula : nr === 22 ? C.flavio : C.elim);
  plot(
    "cPlacar",
    [
      {
        type: "bar", name: "1º turno", x: t1.map((r) => r.NM_URNA_CANDIDATO), y: t1.map((r) => r.votos),
        marker: { color: t1.map((r) => corCand(r.NR_CANDIDATO)), opacity: 0.55 },
        text: t1.map((r) => nf1.format(r.pct_validos) + "%"), textposition: "outside",
        hovertemplate: "%{x}<br>1º turno: %{y:,.0f}<extra></extra>",
      },
      {
        type: "bar", name: "2º turno", x: t2.map((r) => r.NM_URNA_CANDIDATO), y: t2.map((r) => r.votos),
        marker: { color: t2.map((r) => corCand(r.NR_CANDIDATO)) },
        text: t2.map((r) => nf1.format(r.pct_validos) + "%"), textposition: "outside",
        hovertemplate: "%{x}<br>2º turno: %{y:,.0f}<extra></extra>",
      },
    ],
    { barmode: "group", margin: { t: 30, r: 10, b: 110, l: 90 }, yaxis: { title: "votos" }, xaxis: { tickangle: -35, automargin: true } }
  );

  const T1 = D.nacional.turnout.t1, T2 = D.nacional.turnout.t2;
  const comp = [
    ["Lula", N.lula_t1, N.lula_t2, C.lula],
    ["Flávio", N.flavio_t1, N.flavio_t2, C.flavio],
    ["Eliminados", N.eliminados_t1, 0, C.elim],
    ["Brancos/nulos", N.bn_t1, N.bn_t2, C.bn],
    ["Abstenção", T1.QT_ABSTENCOES, T2.QT_ABSTENCOES, C.abs],
  ];
  plot(
    "cComposicao",
    comp.map(([n, a, b, cor]) => ({
      type: "bar", orientation: "h", name: n, y: ["1º turno", "2º turno"], x: [a, b], marker: { color: cor },
      hovertemplate: n + ": %{x:,.0f}<extra></extra>",
    })),
    { barmode: "stack", margin: { t: 40, r: 10, b: 40, l: 70 }, xaxis: { title: "eleitores aptos" } }
  );

  /* 2. Aritmética */
  plot(
    "cPote",
    [
      {
        type: "waterfall", orientation: "v",
        x: ["Eliminados", "Menos brancos/nulos", "Mais comparecimento", "Pote total"],
        measure: ["relative", "relative", "relative", "total"],
        y: [N.eliminados_t1, N.queda_bn, N.delta_comparecimento, 0],
        text: [N.eliminados_t1, N.queda_bn, N.delta_comparecimento, N.pool].map(int),
        textposition: "outside", cliponaxis: false,
        increasing: { marker: { color: C.elim } }, totals: { marker: { color: C.warn } },
        connector: { line: { color: "#3a4d6b" } },
      },
      {
        type: "bar", x: ["→ Lula", "→ Flávio"], y: [N.ganho_lula, N.ganho_flavio],
        marker: { color: [C.lula, C.flavio] }, cliponaxis: false,
        text: [int(N.ganho_lula) + " (" + pct(N.share_pool_lula) + ")", int(N.ganho_flavio) + " (" + pct(N.share_pool_flavio) + ")"],
        textposition: "outside", hovertemplate: "%{x}: %{y:,.0f}<extra></extra>",
      },
    ],
    { showlegend: false, yaxis: { title: "votos", range: [0, N.pool * 1.15] }, xaxis: { tickangle: -25, automargin: true }, margin: { t: 40, r: 10, b: 90, l: 60 } }
  );
  plot(
    "cMargem",
    [
      {
        type: "waterfall",
        x: ["Margem T1 (Lula − Flávio)", "Ganho do Lula", "Ganho do Flávio", "Margem T2"],
        measure: ["absolute", "relative", "relative", "total"],
        y: [N.margem_t1, N.ganho_lula, -N.ganho_flavio, 0],
        text: [N.margem_t1, N.ganho_lula, -N.ganho_flavio, N.margem_t2].map(int), textposition: "outside", cliponaxis: false,
        increasing: { marker: { color: C.lula } }, decreasing: { marker: { color: C.flavio } },
        totals: { marker: { color: C.ok } }, connector: { line: { color: "#3a4d6b" } },
      },
    ],
    { showlegend: false, yaxis: { title: "votos", range: [Math.min(0, N.margem_t1) * 1.4, (N.margem_t1 + N.ganho_lula) * 1.15] }, margin: { t: 40, r: 10, b: 70, l: 70 } }
  );
  plot(
    "cTomada",
    [
      { type: "bar", orientation: "h", y: ["Pote"], x: [N.share_pool_lula * 100], name: "Lula", marker: { color: C.lula },
        text: [pct(N.share_pool_lula)], textposition: "inside" },
      { type: "bar", orientation: "h", y: ["Pote"], x: [N.share_pool_flavio * 100], name: "Flávio", marker: { color: C.flavio },
        text: [pct(N.share_pool_flavio)], textposition: "inside" },
    ],
    {
      barmode: "stack", xaxis: { range: [0, 100], title: "% do pote" }, margin: { t: 40, r: 10, b: 50, l: 50 },
      shapes: [{ type: "line", x0: N.share_pool_necessario_lula * 100, x1: N.share_pool_necessario_lula * 100, y0: -0.5, y1: 0.5,
        line: { color: C.warn, width: 3, dash: "dot" } }],
      annotations: [{ x: N.share_pool_necessario_lula * 100, y: 0.55, text: "mínimo para virar: " + pct(N.share_pool_necessario_lula),
        showarrow: false, font: { color: C.warn } }],
    }
  );

  /* 3. Abstenção */
  const UF = D.uf.slice().sort((a, b) => b.comp_t2_pct - b.comp_t1_pct - (a.comp_t2_pct - a.comp_t1_pct));
  plot(
    "cCompUF",
    [
      { type: "bar", name: "Comparecimento T1", x: UF.map((r) => r.uf), y: UF.map((r) => r.comp_t1_pct), marker: { color: "#5b6b86" } },
      { type: "bar", name: "Comparecimento T2", x: UF.map((r) => r.uf), y: UF.map((r) => r.comp_t2_pct), marker: { color: C.ok } },
      { type: "scatter", mode: "lines+markers", name: "Δ eleitores", x: UF.map((r) => r.uf), y: UF.map((r) => r.delta_comp), yaxis: "y2",
        line: { color: C.warn } },
    ],
    {
      barmode: "group", yaxis: { title: "% comparecimento", range: [60, 90] },
      yaxis2: { title: "Δ eleitores", overlaying: "y", side: "right", showgrid: false }, margin: { t: 40, r: 60, b: 40, l: 55 },
    }
  );
  const simplex = D.fluxo.br.filter((r) => r.metodo === "goodman_simplex");
  const abst = simplex.filter((r) => r.origem === "abstencao_t1").sort((a, b) => b.estimativa - a.estimativa);
  plot(
    "cAbstDestino",
    [
      {
        type: "bar", x: abst.map((r) => r.destino_label), y: abst.map((r) => r.estimativa * 100),
        error_y: { type: "data", symmetric: false, array: abst.map((r) => (r.ci_high - r.estimativa) * 100),
          arrayminus: abst.map((r) => (r.estimativa - r.ci_low) * 100), color: "#dbe5f3" },
        marker: { color: abst.map((r) => (r.destino.includes("lula") ? C.lula : r.destino.includes("flavio") ? C.flavio : r.destino.includes("abst") ? C.abs : C.bn)) },
        text: abst.map((r) => nf1.format(r.estimativa * 100) + "% · " + int(r.votos_estimados)), textposition: "outside",
        hovertemplate: "%{x}: %{y:.1f}%<extra></extra>",
      },
    ],
    { yaxis: { title: "% dos abstencionistas do T1", type: "log", range: [-0.3, 2.15] }, showlegend: false }
  );

  /* 4. Transferências */
  const flows = simplex.filter((r) => (r.votos_estimados || 0) > 50000);
  const nodes = [];
  const idx = (n) => { let i = nodes.indexOf(n); if (i < 0) { nodes.push(n); i = nodes.length - 1; } return i; };
  flows.forEach((r) => { idx(r.origem_label); });
  flows.forEach((r) => { idx(r.destino_label); });
  const nodeColor = (n) => (n.includes("Lula") ? C.lula : n.includes("Flávio") ? C.flavio : n.includes("Abst") ? C.abs : n.includes("Brancos") ? C.bn : C.elim);
  const rgba = (hex, a) => { const v = parseInt(hex.slice(1), 16); return "rgba(" + ((v >> 16) & 255) + "," + ((v >> 8) & 255) + "," + (v & 255) + "," + a + ")"; };
  plot(
    "cSankey",
    [
      {
        type: "sankey", arrangement: "snap",
        node: { label: nodes, color: nodes.map(nodeColor), pad: 14, thickness: 18, line: { color: "#0b1220", width: 1 } },
        link: {
          source: flows.map((r) => idx(r.origem_label)), target: flows.map((r) => idx(r.destino_label)),
          value: flows.map((r) => r.votos_estimados), color: flows.map((r) => rgba(nodeColor(r.destino_label), 0.35)),
          customdata: flows.map((r) => nf1.format(r.estimativa * 100) + "%"),
          hovertemplate: "%{source.label} → %{target.label}<br>%{value:,.0f} votos (%{customdata})<extra></extra>",
        },
      },
    ],
    { margin: { t: 20, r: 20, b: 20, l: 20 } }
  );
  const ordemO = Object.keys({ t1_13_lula: 1, t1_22_flavio_bolsonaro: 1, t1_70_escritor_augusto_cury: 1, t1_14_renan_santos: 1, t1_55_ronaldo_caiado: 1, outros_eliminados_t1: 1, brancos_nulos_t1: 1, abstencao_t1: 1 });
  const tf = simplex.slice().sort((a, b) => ordemO.indexOf(a.origem) - ordemO.indexOf(b.origem) || b.estimativa - a.estimativa);
  table(
    "tFluxo",
    [
      { t: "Origem (1º turno)", l: 1, f: (r) => r.origem_label },
      { t: "Destino (2º turno)", l: 1, f: (r) => r.destino_label },
      { t: "Estimativa", f: (r) => pct(r.estimativa) },
      { t: "IC 95%", f: (r) => pct(r.ci_low) + " – " + pct(r.ci_high) },
      { t: "Votos estimados", f: (r) => int(r.votos_estimados) },
      { t: "Limites possíveis", f: (r) => pct(r.bound_low) + " – " + pct(r.bound_high) },
    ],
    tf
  );

  /* 5. Troca direta */
  const bl = D.fluxo.br.filter((r) => r.metodo === "baseline_proporcional");
  const pick = (o, d) => bl.find((r) => r.origem === o && r.destino === d) || {};
  const tro = [
    ["Lula T1 → Flávio T2", pick("t1_13_lula", "t2_22_flavio_bolsonaro"), C.flavio],
    ["Flávio T1 → Lula T2", pick("t1_22_flavio_bolsonaro", "t2_13_lula"), C.lula],
    ["Lula T1 → Lula T2", pick("t1_13_lula", "t2_13_lula"), C.lula],
    ["Flávio T1 → Flávio T2", pick("t1_22_flavio_bolsonaro", "t2_22_flavio_bolsonaro"), C.flavio],
  ];
  plot(
    "cTroca",
    [
      {
        type: "bar", orientation: "h", y: tro.map((t) => t[0]),
        x: tro.map((t) => ((t[1].bound_high || 0) - (t[1].bound_low || 0)) * 100),
        base: tro.map((t) => (t[1].bound_low || 0) * 100), marker: { color: tro.map((t) => t[2]), opacity: 0.6 },
        text: tro.map((t) => nf1.format((t[1].bound_low || 0) * 100) + "% a " + nf1.format((t[1].bound_high || 0) * 100) + "%"),
        textposition: "inside", hovertemplate: "%{y}<extra></extra>",
      },
    ],
    { xaxis: { title: "% da origem", range: [0, 100] }, margin: { t: 20, r: 20, b: 50, l: 160 }, showlegend: false }
  );

  /* 6. UF */
  const UFL = D.uf.slice().sort((a, b) => b.lula_t2_pct - a.lula_t2_pct);
  plot(
    "cUFLula",
    [
      { type: "bar", name: "Lula T1", x: UFL.map((r) => r.uf), y: UFL.map((r) => r.lula_t1_pct), marker: { color: C.lula, opacity: 0.45 } },
      { type: "bar", name: "Lula T2", x: UFL.map((r) => r.uf), y: UFL.map((r) => r.lula_t2_pct), marker: { color: C.lula } },
    ],
    { barmode: "group", yaxis: { title: "% dos válidos" },
      shapes: [{ type: "line", x0: -0.5, x1: UFL.length - 0.5, y0: 50, y1: 50, line: { color: "#8090a8", dash: "dot" } }] }
  );
  const UFE = D.uf.slice().sort((a, b) => b.excesso_pp - a.excesso_pp);
  plot(
    "cUFExcesso",
    [{ type: "bar", x: UFE.map((r) => r.uf), y: UFE.map((r) => r.excesso_pp), marker: { color: C.ok },
      text: UFE.map((r) => nf1.format(r.excesso_pp)), textposition: "outside",
      hovertemplate: "%{x}: +%{y:.2f} p.p.<extra></extra>" }],
    { yaxis: { title: "p.p. acima do cenário neutro" }, showlegend: false }
  );
  table(
    "tUF",
    [
      { t: "UF", l: 1, f: (r) => r.uf },
      { t: "Lula T1", f: (r) => nf1.format(r.lula_t1_pct) + "%" },
      { t: "Lula T2", f: (r) => nf1.format(r.lula_t2_pct) + "%" },
      { t: "Flávio T1", f: (r) => nf1.format(r.flavio_t1_pct) + "%" },
      { t: "Flávio T2", f: (r) => nf1.format(r.flavio_t2_pct) + "%" },
      { t: "Ganho Lula", f: (r) => int(r.ganho_lula) },
      { t: "Ganho Flávio", f: (r) => int(r.ganho_flavio) },
      { t: "Δ comparecimento", f: (r) => int(r.delta_comp) },
      { t: "Excesso s/ neutro", f: (r) => "+" + nf2.format(r.excesso_pp) + " p.p." },
      { t: "Mun. virados (→Lula/→Flávio)", f: (r) => r.mun_virou_lula + " / " + r.mun_virou_flavio },
      { t: "Vencedor T1→T2", l: 1, f: (r) => (r.vencedor_t1 === r.vencedor_t2 ? esc(r.vencedor_t2) : '<span class="tag sim">' + esc(r.vencedor_t1) + " → " + esc(r.vencedor_t2) + "</span>") },
    ],
    D.uf.slice().sort((a, b) => a.uf.localeCompare(b.uf))
  );

  /* 7. Municípios */
  const P = D.municipios.pontos;
  const grupos = [["sem virada", "#5b6b86"], ["Flávio→Lula", C.lula], ["Lula→Flávio", C.flavio]];
  plot(
    "cMunScatter",
    grupos.map(([g, cor]) => {
      const rows = P.filter((r) => r.virada === g);
      return {
        type: "scattergl", mode: "markers", name: g + " (" + int(rows.length) + ")",
        x: rows.map((r) => r.delta_comp_pp), y: rows.map((r) => r.delta_share_a_pp),
        text: rows.map((r) => r.nm_municipio + "/" + r.uf),
        marker: { color: cor, opacity: g === "sem virada" ? 0.35 : 0.85, size: rows.map((r) => Math.max(4, Math.min(28, Math.sqrt(r.aptos_t2 / 1500)))) },
        hovertemplate: "%{text}<br>Δ comparecimento: %{x:.2f} p.p.<br>Δ Lula: %{y:.2f} p.p.<extra></extra>",
      };
    }),
    { xaxis: { title: "Δ taxa de comparecimento (p.p.)", range: [-10, 15] }, yaxis: { title: "Δ participação do Lula entre os finalistas (p.p.)", range: [-6, 12] } }
  );
  table(
    "tViradas",
    [
      { t: "Município", l: 1, f: (r) => esc(r.nm_municipio) + "/" + r.uf },
      { t: "Virada", l: 1, f: (r) => '<span class="tag sim">' + r.virada + "</span>" },
      { t: "Aptos", f: (r) => int(r.aptos_t2) },
      { t: "Lula T1", f: (r) => int(r.lula_t1) },
      { t: "Flávio T1", f: (r) => int(r.flavio_t1) },
      { t: "Lula T2", f: (r) => int(r.lula_t2) },
      { t: "Flávio T2", f: (r) => int(r.flavio_t2) },
    ],
    D.municipios.viradas.slice(0, 60)
  );

  /* 8. Urnas */
  const H = D.secoes.hist;
  const xb = H.bins.map((b) => b * 100 + 1);
  plot(
    "cHist",
    [
      { type: "scatter", mode: "lines", name: "Flávio T1", x: xb, y: H.flavio_t1, line: { color: C.flavio, dash: "dot", width: 2 } },
      { type: "scatter", mode: "lines", name: "Flávio T2", x: xb, y: H.flavio_t2, line: { color: C.flavio, width: 3 } },
    ],
    {
      xaxis: { title: "% do Flávio na urna (válidos)" }, yaxis: { title: "nº de urnas (faixas de 2%)" },
      shapes: [{ type: "rect", x0: 0, x1: 10, y0: 0, y1: 1, yref: "paper", fillcolor: "rgba(240,180,41,0.12)", line: { width: 0 } }],
      annotations: [{ x: 5, y: 1, yref: "paper", text: "< 10%", showarrow: false, font: { color: C.warn } }],
    }
  );
  const tipos = D.secoes.tipo.slice().sort((a, b) => b.lt10 / b.todas - a.lt10 / a.todas);
  plot(
    "cTipo",
    [{ type: "bar", x: tipos.map((r) => r.tipo), y: tipos.map((r) => (r.lt10 / r.todas) * 100),
      marker: { color: [C.warn, "#d8a44a", "#a98a55", "#5b6b86"] },
      text: tipos.map((r) => nf1.format((r.lt10 / r.todas) * 100) + "% (" + int(r.lt10) + " de " + int(r.todas) + ")"), textposition: "outside",
      hovertemplate: "%{x}<extra></extra>" }],
    { yaxis: { title: "% das urnas com Flávio < 10%", range: [0, 60] }, showlegend: false }
  );
  const S = D.secoes;
  table(
    "tImpacto",
    [
      { t: "Cenário", l: 1, f: (r) => r[0] },
      { t: "Margem do Lula", f: (r) => int(r[1]) },
    ],
    [
      ["Oficial", N.margem_t2],
      ["Sem as " + int(S.flavio_t2.zero) + " urnas com zero", S.margem_sem_zero],
      ["Sem as " + int(S.flavio_t2.lt10) + " urnas abaixo de 10%", S.margem_sem_lt10],
    ]
  );
  table(
    "tBruscas",
    [
      { t: "Local", l: 1, f: (r) => esc(r.nm_municipio) + "/" + r.uf + " · z" + r.nr_zona + " s" + r.nr_secao + "<br><span class='muted'>" + esc(r.local) + "</span>" },
      { t: "Flávio T1", f: (r) => int(r.votos_t1_b) + " (" + pct(r.fb1) + ")" },
      { t: "Flávio T2", f: (r) => int(r.votos_t2_b) + " (" + pct(r.fb2) + ")" },
    ],
    S.bruscas
  );
  table(
    "tZero",
    [
      { t: "Município", l: 1, f: (r) => esc(r.nm_municipio) + "/" + r.uf },
      { t: "Zona/seção", f: (r) => r.nr_zona + " / " + r.nr_secao },
      { t: "Local", l: 1, f: (r) => esc(r.local) },
      { t: "Tipo", l: 1, f: (r) => r.tipo },
      { t: "Válidos T2", f: (r) => int(r.val2) },
      { t: "Lula T2", f: (r) => int(r.votos_t2_a) },
      { t: "Flávio T1", f: (r) => int(r.votos_t1_b) + " de " + int(r.val1) },
    ],
    S.top_zero
  );

  /* 9. Tempo */
  const M = D.tempo.minuto;
  const mx = M.map((r) => ts(r.minuto));
  const gap = D.tempo.gaps[0];
  const gapShape = gap ? [{ type: "rect", x0: ts(gap.inicio), x1: ts(gap.fim), y0: 0, y1: 1, yref: "paper", fillcolor: "rgba(240,180,41,0.13)", line: { width: 0 } }] : [];
  const xr = ["2026-10-25T16:58:00", "2026-10-25T21:40:00"];
  plot(
    "cBus",
    [{ type: "bar", x: mx, y: M.map((r) => r.bus), marker: { color: C.flavio }, hovertemplate: "%{x|%H:%M}: %{y} boletins<extra></extra>" }],
    { xaxis: { type: "date", range: xr, tickformat: "%H:%M" }, yaxis: { title: "boletins/min" }, shapes: gapShape, showlegend: false,
      annotations: gap ? [{ x: "2026-10-25T18:05:00", y: 0.9, yref: "paper", text: gap.minutos + 1 + " min sem recepção", showarrow: false, font: { color: C.warn } }] : [] }
  );
  plot(
    "cCum",
    [
      { type: "scatter", mode: "lines", name: "Lula", x: mx, y: M.map((r) => r.share_lula), line: { color: C.lula, width: 2.5 } },
      { type: "scatter", mode: "lines", name: "Flávio", x: mx, y: M.map((r) => 100 - r.share_lula), line: { color: C.flavio, width: 2.5 } },
    ],
    { xaxis: { type: "date", range: xr, tickformat: "%H:%M" }, yaxis: { title: "% acumulado dos válidos", range: [42, 58] }, shapes: gapShape.concat([{ type: "line", x0: xr[0], x1: xr[1], y0: 50, y1: 50, line: { color: "#8090a8", dash: "dot" } }]) }
  );
  plot(
    "cMarg",
    [
      { type: "scatter", mode: "lines", fill: "tozeroy", name: "margem", x: mx, y: M.map((r) => r.margem),
        line: { color: C.ok }, fillcolor: "rgba(62,207,142,0.18)",
        customdata: M.map((r) => r.pct_apurado), hovertemplate: "%{x|%H:%M}<br>margem: %{y:,.0f}<br>apurado: %{customdata:.1f}%<extra></extra>" },
    ],
    { xaxis: { type: "date", range: xr, tickformat: "%H:%M" }, yaxis: { title: "Lula − Flávio (votos)" }, shapes: gapShape, showlegend: false }
  );
  const B = D.tempo.blocos;
  plot(
    "cRes",
    [
      { type: "bar", name: "resíduo bruto", x: B.map((r) => ts(r.bloco)), y: B.map((r) => r.res_pp), marker: { color: "#9b8cff" } },
      { type: "scatter", mode: "lines+markers", name: "descontado o estado", x: B.map((r) => ts(r.bloco)), y: B.map((r) => r.res_ajust_pp), line: { color: C.ok, width: 3 } },
    ],
    { xaxis: { type: "date", tickformat: "%H:%M" }, yaxis: { title: "p.p.", range: [-1, 4] } }
  );
  const O = D.tempo.ordem_uf;
  plot(
    "cOrdem",
    [{ type: "scatter", mode: "markers+text", x: O.map((r) => ts(r.mediana)), y: O.map((r) => r.share_lula), text: O.map((r) => r.uf), textposition: "top center",
      marker: { size: O.map((r) => Math.max(8, Math.sqrt(r.V / 4e4))), color: O.map((r) => (r.share_lula >= 50 ? C.lula : C.flavio)), opacity: 0.8 },
      hovertemplate: "%{text}: mediana %{x|%H:%M}, Lula %{y:.1f}%<extra></extra>" }],
    { xaxis: { type: "date", tickformat: "%H:%M", range: ["2026-10-25T19:25:00", "2026-10-25T21:05:00"] }, yaxis: { title: "% do Lula no estado" }, showlegend: false,
      shapes: [{ type: "line", x0: "2026-10-25T19:25:00", x1: "2026-10-25T21:05:00", y0: 50, y1: 50, line: { color: "#8090a8", dash: "dot" } }] }
  );

  /* 11. Anomalias */
  table(
    "tAnom",
    [
      { t: "Nível", l: 1, f: (r) => r.nivel },
      { t: "Unidades testadas", f: (r) => int(r.n) },
      { t: "Sinalizadas", f: (r) => int(r.flag) },
      { t: "Falsos positivos esperados", f: (r) => nf1.format(r.fp) },
    ],
    D.anomalias.por_nivel
  );
  table(
    "tAnomMun",
    [
      { t: "Município", l: 1, f: (r) => esc(r.nm_municipio) + "/" + r.uf },
      { t: "Resíduo (p.p.)", f: (r) => '<span class="' + (r.residuo_pp > 0 ? "pos" : "neg") + '">' + nf2.format(r.residuo_pp) + "</span>" },
      { t: "Studentizado", f: (r) => nf1.format(r.residuo_student) },
      { t: "q (FDR)", f: (r) => (r.q_fdr < 0.001 ? r.q_fdr.toExponential(1) : nf3.format(r.q_fdr)) },
    ],
    D.anomalias.top_mun
  );

  function resizeAll() {
    charts.forEach((el) => { try { Plotly.Plots.resize(el); } catch (_e) { /* noop */ } });
  }
  window.addEventListener("resize", resizeAll);
  setTimeout(resizeAll, 200);
  window.__ESTUDO_OK__ = charts.length;
})();
