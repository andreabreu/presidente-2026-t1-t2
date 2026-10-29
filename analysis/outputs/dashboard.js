/* global Plotly, window, document */
(function () {
  "use strict";

  const D = window.DASH;
  if (!D || !window.Plotly) {
    document.body.insertAdjacentHTML(
      "afterbegin",
      '<div style="padding:1rem;background:#4a2222;color:#fff">Falha: Plotly ou dados DASH ausentes.</div>'
    );
    return;
  }

  const fmt = (n) =>
    n == null || Number.isNaN(Number(n))
      ? "—"
      : Number(n).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
  const pct = (n) =>
    n == null || Number.isNaN(Number(n))
      ? "—"
      : (Number(n) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + "%";
  const pp = (n) =>
    n == null || Number.isNaN(Number(n))
      ? "—"
      : Number(n).toLocaleString("pt-BR", { maximumFractionDigits: 2 });

  const ufSel = document.getElementById("fUF");
  const munSel = document.getElementById("fMun");
  const porteSel = document.getElementById("fPorte");

  function uniqueSorted(values) {
    return [...new Set(values.filter((v) => v != null && v !== ""))].sort((a, b) =>
      String(a).localeCompare(String(b), "pt")
    );
  }

  function fillSelect(sel, values, placeholder) {
    const current = sel.value;
    sel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = placeholder;
    sel.appendChild(opt0);
    values.forEach((v) => {
      const o = document.createElement("option");
      o.value = String(v);
      o.textContent = String(v);
      sel.appendChild(o);
    });
    if ([...sel.options].some((o) => o.value === current)) sel.value = current;
  }

  fillSelect(
    ufSel,
    uniqueSorted(D.uf.map((r) => r.SG_UF)),
    "Brasil (todas)"
  );
  fillSelect(
    porteSel,
    uniqueSorted(D.mun.map((r) => r.porte)),
    "Todos"
  );

  function munOptionsForUf(uf) {
    if (!uf) return [];
    const rows = D.mun.filter((r) => r.uf === uf);
    return uniqueSorted(rows.map((r) => r.nm_municipio)).map((name) => {
      const sample = rows.find((r) => r.nm_municipio === name);
      return {
        value: String(sample.cd_municipio),
        label: name,
        uf: sample.uf,
      };
    });
  }

  function refreshMunicipioSelect() {
    const uf = ufSel.value;
    const opts = munOptionsForUf(uf);
    const current = munSel.value;
    munSel.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = uf
      ? "Todos municípios de " + uf
      : "Selecione uma UF primeiro";
    munSel.appendChild(opt0);
    opts.forEach((item) => {
      const o = document.createElement("option");
      o.value = item.value;
      o.textContent = item.label;
      o.dataset.uf = item.uf;
      munSel.appendChild(o);
    });
    if ([...munSel.options].some((o) => o.value === current)) munSel.value = current;
    else munSel.value = "";
    munSel.disabled = !uf;
  }

  refreshMunicipioSelect();
  document.getElementById("caveats").innerHTML =
    "<strong>Ressalvas:</strong> " + D.caveats.join(" · ");

  function filters() {
    return {
      turno: document.getElementById("fTurno").value,
      cenario: document.getElementById("fCenario").value,
      uf: ufSel.value,
      munCode: munSel.value,
      porte: porteSel.value,
      top: parseInt(document.getElementById("fTop").value, 10),
      sort: document.getElementById("fSort").value,
      search: document.getElementById("fSearch").value.trim().toLowerCase(),
    };
  }

  function munFiltered() {
    const f = filters();
    let rows = D.mun.slice();
    if (f.uf) rows = rows.filter((r) => r.uf === f.uf);
    if (f.munCode) rows = rows.filter((r) => String(r.cd_municipio) === f.munCode);
    if (f.porte) rows = rows.filter((r) => r.porte === f.porte);
    if (f.cenario === "com_virada") rows = rows.filter((r) => r.virada_finalistas);
    if (f.cenario === "sem_virada") rows = rows.filter((r) => !r.virada_finalistas);
    if (f.search) {
      rows = rows.filter((r) =>
        String(r.nm_municipio || "")
          .toLowerCase()
          .includes(f.search)
      );
    }
    return rows;
  }

  function ufFiltered() {
    const f = filters();
    let rows = D.uf.slice();
    if (f.uf) rows = rows.filter((r) => r.SG_UF === f.uf);
    return rows;
  }

  function renderKpis() {
    const rows = munFiltered();
    const sum = (k) => rows.reduce((a, r) => a + (Number(r[k]) || 0), 0);
    const k = D.kpis;
    const scoped =
      filters().uf ||
      filters().cenario !== "todos" ||
      filters().munCode ||
      filters().porte ||
      filters().search;
    const cards = scoped
      ? [
          ["Municípios", fmt(rows.length)],
          ["Comparecimento T1", fmt(sum("comp_t1"))],
          ["Comparecimento T2", fmt(sum("comp_t2"))],
          ["Δ comparecimento", fmt(sum("delta_comp"))],
          ["Abstenção T1", fmt(sum("abstencao_t1"))],
          ["Abstenção T2", fmt(sum("abstencao_t2"))],
          ["Abst.→voto (proxy)", fmt(sum("abstencao_que_votou_proxy"))],
          ["Mun. com virada", fmt(rows.filter((r) => r.virada_finalistas).length)],
        ]
      : [
          ["Aptos T1", fmt(k.aptos_t1)],
          ["Aptos T2", fmt(k.aptos_t2)],
          ["Comparecimento T1", fmt(k.comp_t1) + " (" + pct(k.taxa_comp_t1) + ")"],
          ["Comparecimento T2", fmt(k.comp_t2) + " (" + pct(k.taxa_comp_t2) + ")"],
          ["Abstenção T1", fmt(k.abst_t1)],
          ["Abstenção T2", fmt(k.abst_t2)],
          ["Abst.→voto (proxy)", fmt(k.abst_que_votou_proxy)],
          ["Δ comparecimento", fmt(k.comp_t2 - k.comp_t1)],
        ];
    document.getElementById("kpis").innerHTML = cards
      .map(
        ([l, v]) =>
          '<div class="kpi"><div class="v">' + v + '</div><div class="l">' + l + "</div></div>"
      )
      .join("");
  }

  const layoutBase = {
    autosize: true,
    paper_bgcolor: "#152238",
    plot_bgcolor: "#152238",
    font: { color: "#d7e3f4", size: 11 },
    margin: { t: 36, r: 20, b: 60, l: 55 },
    legend: { orientation: "h", y: 1.15 },
  };
  const cfg = { responsive: true, displayModeBar: false };
  const CHART_IDS = [
    "cPlacar",
    "cUfTurnout",
    "cUfAbstBack",
    "cUfSwing",
    "cUfFlip",
    "cFluxo",
    "cMunRank",
    "cScatter",
    "cScatter2",
  ];

  function containerWidth(id) {
    const el = document.getElementById(id);
    if (!el) return 400;
    const card = el.closest(".card") || el.parentElement || el;
    const w = Math.floor(card.getBoundingClientRect().width - 16);
    return Math.max(280, Math.min(w, window.innerWidth - 24));
  }

  function mergeLayout(id, extra) {
    return Object.assign({}, layoutBase, { width: containerWidth(id) }, extra || {});
  }

  function resizeCharts() {
    CHART_IDS.forEach((id) => {
      const el = document.getElementById(id);
      if (el && el.data) {
        try {
          Plotly.relayout(el, { width: containerWidth(id), autosize: true });
          Plotly.Plots.resize(el);
        } catch (_err) {
          /* ignore */
        }
      }
    });
  }

  function renderPlacar() {
    const f = filters();
    let rows = D.placar.slice().sort((a, b) => a.rank - b.rank);
    if (f.turno === "1") rows = rows.filter((r) => r.NR_TURNO === 1);
    if (f.turno === "2") rows = rows.filter((r) => r.NR_TURNO === 2);
    const t1 = rows.filter((r) => r.NR_TURNO === 1);
    const t2 = rows.filter((r) => r.NR_TURNO === 2);
    const traces = [];
    if (f.turno !== "2") {
      traces.push({
        type: "bar",
        name: "T1",
        x: t1.map((r) => r.NM_URNA_CANDIDATO),
        y: t1.map((r) => r.votos),
        text: t1.map((r) => pp(r.pct_validos) + "%"),
        textposition: "auto",
      });
    }
    if (f.turno !== "1") {
      traces.push({
        type: "bar",
        name: "T2",
        x: t2.map((r) => r.NM_URNA_CANDIDATO),
        y: t2.map((r) => r.votos),
        text: t2.map((r) => pp(r.pct_validos) + "%"),
        textposition: "auto",
      });
    }
    Plotly.newPlot(
      "cPlacar",
traces,
      mergeLayout("cPlacar", { barmode: "group", yaxis: { title: "Votos" } }),
      cfg
    );
  }

  function renderUfTurnout() {
    const rows = ufFiltered()
      .slice()
      .sort((a, b) => (b.taxa_comparecimento_t2 || 0) - (a.taxa_comparecimento_t2 || 0));
    const x = rows.map((r) => r.SG_UF);
    Plotly.newPlot(
      "cUfTurnout",
[
        { type: "bar", name: "Comp T1 %", x: x, y: rows.map((r) => r.taxa_comparecimento_t1) },
        { type: "bar", name: "Comp T2 %", x: x, y: rows.map((r) => r.taxa_comparecimento_t2) },
        { type: "bar", name: "Abst T1 %", x: x, y: rows.map((r) => r.taxa_abstencao_t1) },
        { type: "bar", name: "Abst T2 %", x: x, y: rows.map((r) => r.taxa_abstencao_t2) },
      ],
      mergeLayout("cUfTurnout", { barmode: "group", yaxis: { title: "%" } }),
      cfg
    );
  }

  function renderUfAbstBack() {
    const rows = ufFiltered()
      .slice()
      .sort((a, b) => (b.abstencao_que_votou_proxy || 0) - (a.abstencao_que_votou_proxy || 0));
    Plotly.newPlot(
      "cUfAbstBack",
[
        {
          type: "bar",
          name: "Abst.→voto proxy",
          x: rows.map((r) => r.SG_UF),
          y: rows.map((r) => r.abstencao_que_votou_proxy),
          marker: { color: "#3ecf8e" },
        },
        {
          type: "bar",
          name: "Novos abstentos proxy",
          x: rows.map((r) => r.SG_UF),
          y: rows.map((r) => r.novos_abstentos_proxy),
          marker: { color: "#f0b429" },
        },
        {
          type: "scatter",
          mode: "lines+markers",
          name: "Δ comp",
          x: rows.map((r) => r.SG_UF),
          y: rows.map((r) => r.delta_comparecimento),
          yaxis: "y2",
        },
      ],
      mergeLayout("cUfAbstBack", {
        yaxis: { title: "Eleitores" },
        yaxis2: { title: "Δ comp", overlaying: "y", side: "right", showgrid: false },
      }),
      cfg
    );
  }

  function renderUfSwing() {
    const rows = ufFiltered()
      .slice()
      .sort((a, b) => (b.delta_share_a_pp_pond || 0) - (a.delta_share_a_pp_pond || 0));
    Plotly.newPlot(
      "cUfSwing",
[
        {
          type: "bar",
          x: rows.map((r) => r.SG_UF),
          y: rows.map((r) => r.delta_share_a_pp_pond),
          marker: {
            color: rows.map((r) => ((r.delta_share_a_pp_pond || 0) >= 0 ? "#4da3ff" : "#e36b6b")),
          },
          name: "Δ share A pond. (p.p.)",
        },
      ],
      mergeLayout("cUfSwing", { yaxis: { title: "p.p." } }),
      cfg
    );
  }

  function renderUfFlip() {
    const rows = ufFiltered();
    const flipped = rows.filter((r) => r.virada_uf);
    const kept = rows.filter((r) => !r.virada_uf);
    Plotly.newPlot(
      "cUfFlip",
[
        {
          type: "bar",
          orientation: "h",
          y: ["Sem virada UF", "Com virada UF"],
          x: [kept.length, flipped.length],
          hovertext: [
            kept.map((r) => r.SG_UF + ": " + r.vencedor_t1 + "→" + r.vencedor_t2).join("<br>"),
            flipped.map((r) => r.SG_UF + ": " + r.vencedor_t1 + "→" + r.vencedor_t2).join("<br>"),
          ],
          hoverinfo: "text+x",
          marker: { color: ["#3ecf8e", "#f0b429"] },
        },
      ],
      mergeLayout("cUfFlip", { margin: Object.assign({}, layoutBase.margin, { l: 110 }) }),
      cfg
    );
  }

  function renderFluxo() {
    const rows = (D.fluxo || []).slice(0, 40);
    if (!rows.length) {
      Plotly.newPlot(
      "cFluxo",
[],
        mergeLayout("cFluxo", {
          annotations: [
            {
              text: "Fluxo nacional não disponível neste recorte",
              showarrow: false,
              font: { color: "#93a4bd" },
            },
          ],
        }),
        cfg
      );
      return;
    }
    Plotly.newPlot(
      "cFluxo",
[
        {
          type: "bar",
          orientation: "h",
          y: rows.map((r) => (r.origem + " → " + r.destino).slice(0, 48)),
          x: rows.map((r) => r.votos_estimados ?? r.estimativa),
        },
      ],
      mergeLayout("cFluxo", { margin: Object.assign({}, layoutBase.margin, { l: 180 }) }),
      cfg
    );
  }

  function topMun() {
    const f = filters();
    const key = f.sort;
    return munFiltered()
      .slice()
      .sort((a, b) => (Number(b[key]) || 0) - (Number(a[key]) || 0))
      .slice(0, f.top);
  }

  function renderMunRank() {
    const rows = topMun();
    const f = filters();
    const y = rows.map((r) => r.nm_municipio + "/" + r.uf).reverse();
    const x = rows.map((r) => r[f.sort]).reverse();
    Plotly.newPlot(
      "cMunRank",
[
        {
          type: "bar",
          orientation: "h",
          y: y,
          x: x,
          marker: {
            color: rows.map((r) => (r.virada_finalistas ? "#f0b429" : "#4da3ff")).reverse(),
          },
          hovertext: rows
            .map(
              (r) =>
                r.nm_municipio +
                "/" +
                r.uf +
                "<br>virada=" +
                r.virada_finalistas +
                "<br>ΔshareA=" +
                pp(r.delta_share_a_pp) +
                "<br>abst→voto=" +
                fmt(r.abstencao_que_votou_proxy)
            )
            .reverse(),
          hoverinfo: "text",
        },
      ],
      mergeLayout("cMunRank", {
        height: Math.max(320, rows.length * 14),
        margin: { t: 20, r: 20, b: 40, l: 140 },
      }),
      cfg
    );
  }

  function renderScatter() {
    const rows = munFiltered();
    Plotly.newPlot(
      "cScatter",
[
        {
          type: "scattergl",
          mode: "markers",
          x: rows.map((r) => r.delta_comp_pp),
          y: rows.map((r) => r.delta_share_a_pp),
          text: rows.map((r) => r.nm_municipio + "/" + r.uf),
          marker: {
            size: rows.map((r) => Math.max(5, Math.sqrt((r.aptos_t2 || 1) / 800))),
            color: rows.map((r) => (r.virada_finalistas ? 1 : 0)),
            colorscale: [
              [0, "#4da3ff"],
              [1, "#f0b429"],
            ],
            opacity: 0.7,
          },
        },
      ],
      mergeLayout("cScatter", {
        xaxis: { title: "Δ taxa comparecimento (p.p.)" },
        yaxis: { title: "Δ share A (p.p.)" },
      }),
      cfg
    );
  }

  function renderScatter2() {
    const rows = munFiltered();
    Plotly.newPlot(
      "cScatter2",
[
        {
          type: "scattergl",
          mode: "markers",
          x: rows.map((r) => ((r.abstencao_t1 || 0) / (r.aptos_t1 || 1)) * 100),
          y: rows.map((r) => (r.share_a_t2_valid || 0) * 100),
          text: rows.map((r) => r.nm_municipio + "/" + r.uf),
          marker: {
            size: 7,
            opacity: 0.65,
            color: rows.map((r) => r.abstencao_que_votou_proxy || 0),
            colorscale: "Viridis",
            colorbar: { title: "abst→voto" },
          },
        },
      ],
      mergeLayout("cScatter2", {
        xaxis: { title: "Abstenção T1 (%)" },
        yaxis: { title: "Share A no T2 (%)" },
      }),
      cfg
    );
  }

  function renderTable() {
    const rows = topMun();
    const cols = [
      "uf",
      "nm_municipio",
      "cenario",
      "aptos_t2",
      "comp_t1",
      "comp_t2",
      "delta_comp",
      "abstencao_t1",
      "abstencao_t2",
      "abstencao_que_votou_proxy",
      "delta_share_a_pp",
      "votos_t2_a",
      "votos_t2_b",
    ];
    let html =
      '<table class="dt"><thead><tr>' +
      cols.map((c) => "<th>" + c + "</th>").join("") +
      "</tr></thead><tbody>";
    rows.forEach((r) => {
      html +=
        "<tr>" +
        cols
          .map((c) => {
            const v = r[c];
            const text =
              typeof v === "number" ? (Math.abs(v) >= 1000 ? fmt(v) : pp(v)) : v == null ? "" : v;
            return "<td>" + text + "</td>";
          })
          .join("") +
        "</tr>";
    });
    html += "</tbody></table>";
    document.getElementById("tbl").innerHTML = html;
  }

  function redraw() {
    renderKpis();
    renderPlacar();
    renderUfTurnout();
    renderUfAbstBack();
    renderUfSwing();
    renderUfFlip();
    renderFluxo();
    renderMunRank();
    renderScatter();
    renderScatter2();
    renderTable();
    requestAnimationFrame(function () {
      resizeCharts();
      setTimeout(resizeCharts, 50);
      setTimeout(resizeCharts, 250);
    });
  }

  ufSel.addEventListener("change", function () {
    refreshMunicipioSelect();
    redraw();
  });
  [
    "fTurno",
    "fCenario",
    "fMun",
    "fPorte",
    "fTop",
    "fSort",
    "fSearch",
  ].forEach((id) => {
    document.getElementById(id).addEventListener("change", redraw);
    document.getElementById(id).addEventListener("input", redraw);
  });

  window.addEventListener("resize", resizeCharts);
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(resizeCharts);
    CHART_IDS.forEach((id) => {
      const el = document.getElementById(id);
      if (el) ro.observe(el);
    });
  }

  redraw();
  window.__DASH_OK__ = true;
  window.__DASH_RESIZE__ = resizeCharts;
})();
