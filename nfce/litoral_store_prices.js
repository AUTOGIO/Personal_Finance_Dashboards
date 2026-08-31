(() => {
  const $ = (sel) => document.querySelector(sel);
  const fmtPct = (v) => (v == null || Number.isNaN(v) ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(1)}%`);
  const fmtMoney = (v) =>
    v == null
      ? "—"
      : Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 2 });
  const pctClass = (v) => (v == null ? "" : v > 0 ? "pct-up" : v < 0 ? "pct-down" : "");

  function parseEmbedded(id) {
    const node = document.getElementById(id);
    if (!node) return null;
    const raw = node.textContent.replace(/^\/\*__\w+__\*\//, "").replace(/\/\*__END_\w+__\*\/$/, "").trim();
    if (!raw || raw === "{}") return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  async function loadData() {
    try {
      const [dataRes, valRes] = await Promise.all([
        fetch("./litoral_price_data.json", { cache: "no-store" }),
        fetch("./litoral_price_validation.json", { cache: "no-store" }),
      ]);
      if (dataRes.ok) {
        return {
          data: await dataRes.json(),
          validation: valRes.ok ? await valRes.json() : parseEmbedded("fallback-validation"),
        };
      }
    } catch (_) {
      /* file:// or offline — use embedded */
    }
    return {
      data: parseEmbedded("fallback-data"),
      validation: parseEmbedded("fallback-validation"),
    };
  }

  function setNav() {
    document.querySelectorAll(".nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("is-active", b === btn));
        document.querySelectorAll(".view").forEach((panel) => {
          panel.classList.toggle("is-active", panel.getAttribute("data-view-panel") === btn.dataset.view);
        });
      });
    });
  }

  function renderKpis(data) {
    const k = data.kpis || {};
    const items = [
      { lbl: "Notas (loja)", val: k.receipts?.toLocaleString("pt-BR"), det: `xml ${k.xml_receipts ?? "—"} · txt ${k.txt_receipts ?? "—"}` },
      { lbl: "Snapshots", val: k.snapshots, det: `${k.first_snapshot || "?"} → ${k.last_snapshot || "?"}` },
      { lbl: "Produtos ≥2 anos", val: k.tracked_products?.toLocaleString("pt-BR"), det: "mediana por ano" },
      { lbl: "Staples", val: `${k.staples_found}/8`, det: "cesta básica" },
      { lbl: "Cesta vs base", val: fmtPct(k.basket_cum_pct), det: "geom. Dec anos" },
      { lbl: "Gasto amostral", val: fmtMoney(k.total_spend), det: "soma das NFC-e" },
    ];
    $("#kpis").innerHTML = items
      .map(
        (item) =>
          `<div class="kpi"><div class="lbl">${item.lbl}</div><div class="val">${item.val ?? "—"}</div><div class="det">${item.det}</div></div>`
      )
      .join("");
  }

  function svgLine(series, opts = {}) {
    const w = 640;
    const h = 220;
    const pad = { t: 16, r: 16, b: 28, l: 40 };
    const values = series.flatMap((s) => s.points.map((p) => p.v));
    if (!values.length) return `<p class="muted">Sem dados.</p>`;
    const min = Math.min(...values) * 0.98;
    const max = Math.max(...values) * 1.02;
    const years = [...new Set(series.flatMap((s) => s.points.map((p) => p.year)))].sort();
    const x = (year) => pad.l + ((year - years[0]) / Math.max(1, years[years.length - 1] - years[0])) * (w - pad.l - pad.r);
    const y = (v) => pad.t + (1 - (v - min) / Math.max(1e-9, max - min)) * (h - pad.t - pad.b);
    const paths = series
      .map((s) => {
        const d = s.points
          .map((p, i) => `${i ? "L" : "M"}${x(p.year).toFixed(1)},${y(p.v).toFixed(1)}`)
          .join(" ");
        return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.4"/>`;
      })
      .join("");
    const labels = years
      .map((year) => `<text x="${x(year)}" y="${h - 8}" text-anchor="middle" fill="currentColor" font-size="11">${year}</text>`)
      .join("");
    return `<svg class="${opts.className || "line-chart"}" viewBox="0 0 ${w} ${h}" role="img">${paths}${labels}</svg>`;
  }

  function renderBasket(data) {
    const basket = data.basket_index || [];
    const litoral = basket.map((p) => ({ year: p.year, v: p.v }));
    let ipca = [];
    if (basket.length) {
      let v = 100;
      ipca = basket.map((p, i) => {
        if (i === 0) return { year: p.year, v: 100 };
        const rate = (p.ipca ?? 4.5) / 100;
        v *= 1 + rate;
        return { year: p.year, v: Math.round(v * 100) / 100 };
      });
    }
    $("#chart-basket").innerHTML = svgLine(
      [
        { color: "var(--s1)", points: litoral },
        { color: "var(--ipca)", points: ipca },
      ],
      { className: "line-chart" }
    );
  }

  function renderSnapshots(data) {
    const rows = data.snapshots || [];
    $("#snapshots").innerHTML = `
      <table class="table">
        <thead><tr><th>Ano</th><th>Dia modal</th><th>Notas</th><th>YoY</th></tr></thead>
        <tbody>
          ${rows
            .map(
              (r) => `<tr>
                <td>${r.year}</td>
                <td>${r.mode_date}</td>
                <td>${r.total_receipts.toLocaleString("pt-BR")}</td>
                <td>${r.yoy_eligible ? '<span class="badge">ok</span>' : '<span class="badge warn">naming drift</span>'}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
  }

  function renderStaples(data) {
    const staples = (data.staples || []).filter((s) => s.found);
    const colors = ["#1d6fd1", "#c54231", "#1d7d43", "#8e8574", "#7a4fb3", "#d17a1d", "#2a9d8f", "#e76f51"];
    const series = staples.map((s, i) => ({
      color: colors[i % colors.length],
      points: (s.series || [])
        .filter((p) => p.yoy_eligible)
        .map((p) => ({ year: p.year, v: p.price })),
    }));
    $("#chart-staples").innerHTML = svgLine(series, { className: "multi-chart" });
    $("#staples-table").innerHTML = `
      <table class="table">
        <thead><tr><th>Item</th><th>Produto</th><th>De→Até</th><th>Δ acum.</th><th>CAGR</th></tr></thead>
        <tbody>
          ${staples
            .map(
              (s) => `<tr>
                <td><b>${s.label}</b></td>
                <td>${s.desc || "—"}</td>
                <td class="muted">${s.from_year}→${s.to_year}<br>${fmtMoney(s.p_first)} → ${fmtMoney(s.p_last)}</td>
                <td class="${pctClass(s.cum_pct)}">${fmtPct(s.cum_pct)}</td>
                <td class="${pctClass(s.cagr_pct)}">${fmtPct(s.cagr_pct)}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
  }

  function moverList(rows) {
    return (rows || [])
      .map(
        (r) => `<div class="insight">
          <div><b>${r.desc}</b><div class="muted">${r.from_year}→${r.to_year} · ${r.uom}</div></div>
          <div class="${pctClass(r.cagr_pct)}">${fmtPct(r.cagr_pct)}/ano</div>
        </div>`
      )
      .join("");
  }

  function renderCompare(data) {
    const rows = data.compare_personal || [];
    if (!rows.length) {
      $("#compare-table").innerHTML =
        `<p class="muted">Gere <code>personal_inflation_data.json</code> e rode de novo o script Litoral para preencher este painel.</p>`;
      return;
    }
    $("#compare-table").innerHTML = `
      <table class="table">
        <thead><tr><th>Staple</th><th>Loja (Litoral)</th><th>Pessoal</th><th>Δ loja</th><th>Δ pessoal</th></tr></thead>
        <tbody>
          ${rows
            .map(
              (r) => `<tr>
                <td><b>${r.label}</b></td>
                <td>${r.litoral_desc || '<span class="muted">não encontrado</span>'}
                  <div class="muted">${r.litoral_from || "?"}→${r.litoral_to || "?"}</div></td>
                <td>${r.personal_desc || '<span class="muted">sem match</span>'}
                  <div class="muted">${r.personal_from || "?"}→${r.personal_to || "?"}</div></td>
                <td class="${pctClass(r.litoral_cagr_pct)}">${fmtPct(r.litoral_cagr_pct)} <span class="muted">CAGR</span></td>
                <td class="${pctClass(r.personal_ann_pct)}">${fmtPct(r.personal_ann_pct)} <span class="muted">a.a.</span></td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
  }

  function renderProducts(data) {
    const all = data.products || [];
    const draw = (filter = "") => {
      const q = filter.trim().toUpperCase();
      const rows = q ? all.filter((r) => (r.desc || "").toUpperCase().includes(q)) : all;
      $("#products-table").innerHTML = `
        <table class="table">
          <thead><tr><th>Produto</th><th>Anos</th><th>Δ</th><th>CAGR</th><th>Gasto</th></tr></thead>
          <tbody>
            ${rows
              .slice(0, 200)
              .map(
                (r) => `<tr>
                  <td>${r.desc}<div class="muted">${r.cat} · ${r.uom}${r.has_naming_drift_year ? " · tem 2026" : ""}</div></td>
                  <td>${r.from_year}→${r.to_year}</td>
                  <td class="${pctClass(r.cum_pct)}">${fmtPct(r.cum_pct)}</td>
                  <td class="${pctClass(r.cagr_pct)}">${fmtPct(r.cagr_pct)}</td>
                  <td>${fmtMoney(r.spend)}</td>
                </tr>`
              )
              .join("")}
          </tbody>
        </table>`;
    };
    draw();
    $("#product-filter").addEventListener("input", (e) => draw(e.target.value));
  }

  async function main() {
    setNav();
    const { data, validation } = await loadData();
    if (!data || !data.kpis) {
      $("#subtitle").textContent = "Rode python3 litoral_store_prices.py para gerar os dados.";
      return;
    }
    $("#subtitle").textContent = data.generated_from || "";
    $("#sampling-note").textContent = data.sampling_note || "";
    $("#updated-badge").textContent = `${data.kpis.snapshots || 0} snapshots`;
    const dirs = validation?.validation?.xml_directories?.length;
    if (dirs) $("#source-badge").textContent = `${dirs} pastas NFCE_XML_*`;
    renderKpis(data);
    renderBasket(data);
    renderSnapshots(data);
    renderStaples(data);
    $("#risers").innerHTML = moverList(data.risers);
    $("#fallers").innerHTML = moverList(data.fallers);
    renderCompare(data);
    renderProducts(data);
  }

  main();
})();
