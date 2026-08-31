(function(){
  const DATA_PATH = "./personal_inflation_data.json";
  const VALIDATION_PATH = "./personal_inflation_validation.json";
  const NS = "http://www.w3.org/2000/svg";

  const state = {
    view: "overview",
    data: null,
    validation: null,
    query: "",
    category: "all",
    merchant: "all",
    fromMonth: "all",
    toMonth: "all",
    sort: "spend-desc",
    limit: 40,
    selectedProduct: null,
  };

  const els = {
    subtitle: document.getElementById("subtitle"),
    sourceBadge: document.getElementById("source-badge"),
    updatedBadge: document.getElementById("updated-badge"),
    navButtons: Array.from(document.querySelectorAll(".nav-btn")),
    views: Array.from(document.querySelectorAll(".view")),
    kpis: document.getElementById("kpis"),
    insights: document.getElementById("insights"),
    chartIndex: document.getElementById("chart-index"),
    chartYoy: document.getElementById("chart-yoy"),
    chartCats: document.getElementById("chart-cats"),
    risers: document.getElementById("risers"),
    fallers: document.getElementById("fallers"),
    prodNote: document.getElementById("prod-note"),
    search: document.getElementById("search"),
    categoryFilter: document.getElementById("category-filter"),
    merchantFilter: document.getElementById("merchant-filter"),
    fromFilter: document.getElementById("from-filter"),
    toFilter: document.getElementById("to-filter"),
    sortFilter: document.getElementById("sort-filter"),
    resultsNote: document.getElementById("results-note"),
    prodBody: document.querySelector("#prod-table tbody"),
    moreBtn: document.getElementById("more-btn"),
    productDetail: document.getElementById("product-detail"),
    validationKpis: document.getElementById("validation-kpis"),
    validationSummary: document.getElementById("validation-summary"),
    groundTruth: document.getElementById("ground-truth"),
    validationExamples: document.getElementById("validation-examples"),
    tip: document.getElementById("tip"),
  };

  function css(name){ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function fmt(n, d){
    if (n == null || Number.isNaN(Number(n))) return "–";
    const decimals = d == null ? 1 : d;
    return Number(n).toLocaleString("pt-BR", {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
  }
  function pct(n, d){
    if (n == null || Number.isNaN(Number(n))) return "–";
    return (n > 0 ? "+" : "") + fmt(n, d == null ? 1 : d) + "%";
  }
  function brl(n){ return "R$ " + fmt(n, 2); }
  function mNice(m){
    const [y, mm] = m.split("-");
    return ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"][Number(mm) - 1] + "/" + y.slice(2);
  }
  function showTip(html, x, y){
    els.tip.innerHTML = html;
    els.tip.style.display = "block";
    const rect = els.tip.getBoundingClientRect();
    els.tip.style.left = Math.min(x + 14, window.innerWidth - rect.width - 8) + "px";
    els.tip.style.top = Math.max(8, y - rect.height - 12) + "px";
  }
  function hideTip(){ els.tip.style.display = "none"; }
  function svgEl(tag, attrs){
    const node = document.createElementNS(NS, tag);
    Object.keys(attrs).forEach((key) => node.setAttribute(key, attrs[key]));
    return node;
  }
  function parseFallback(id, start, end){
    const raw = (document.getElementById(id)?.textContent || "").trim();
    const cleaned = raw.replace(start, "").replace(end, "").trim();
    if (!cleaned) return null;
    try { return JSON.parse(cleaned); } catch (_) { return null; }
  }

  async function loadJson(path){
    const response = await fetch(path, {cache: "no-store"});
    if (!response.ok) throw new Error(path + ": " + response.status);
    return response.json();
  }

  async function boot(){
    const fallbackData = parseFallback("fallback-data", "/*__DATA__*/", "/*__END_DATA__*/");
    const fallbackValidation = parseFallback("fallback-validation", "/*__VALIDATION__*/", "/*__END_VALIDATION__*/");
    state.data = fallbackData;
    state.validation = fallbackValidation;
    renderAll();

    try {
      const [data, validation] = await Promise.all([loadJson(DATA_PATH), loadJson(VALIDATION_PATH)]);
      state.data = data;
      state.validation = validation;
      renderAll();
    } catch (_) {
      if (!state.data) {
        document.body.innerHTML = '<p style="padding:40px;font-family:system-ui">Sem dados. Rode <code>python3 personal_inflation.py</code> ou sirva esta pasta por HTTP.</p>';
      }
    }
  }

  function renderAll(){
    if (!state.data) return;
    renderNav();
    renderHeader();
    renderOverview();
    renderProductFilters();
    renderProducts();
    renderValidation();
  }

  function renderNav(){
    els.navButtons.forEach((button) => {
      const active = button.dataset.view === state.view;
      button.classList.toggle("is-active", active);
    });
    els.views.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.viewPanel === state.view);
    });
  }

  function renderHeader(){
    const data = state.data;
    const validation = state.validation;
    els.subtitle.textContent =
      "Calculado a partir de " + data.generated_from + " · " + data.kpis.tracked_products +
      " produtos rastreados cobrindo " + fmt(data.kpis.coverage_pct, 1) + "% de " +
      brl(data.kpis.total_spend) + " em compras.";
    els.sourceBadge.textContent = validation?.source_of_truth || "Fonte: XMLs em notas/";
    const lastMonth = data.kpis.last_month ? mNice(data.kpis.last_month) : "–";
    els.updatedBadge.textContent = "Último mês: " + lastMonth;
  }

  function renderOverview(){
    renderKpis();
    renderInsights();
    renderIndexChart();
    renderYearChart();
    renderCategoryChart();
    renderMoverTables();
  }

  function renderKpis(){
    const k = state.data.kpis;
    const cards = [
      ["Inflação acumulada", pct(k.cum_pct), "desde " + mNice(state.data.index[0].m)],
      ["Taxa anualizada", pct(k.ann_pct, 2) + " a.a.", "média de todo o período"],
      ["Últimos 12 meses", pct(k.yoy12_pct, 2), "até " + mNice(k.last_month)],
      ["Notas fiscais", k.receipts.toLocaleString("pt-BR"), "canceladas excluídas"],
      ["Produtos rastreados", k.tracked_products.toLocaleString("pt-BR"), "comprados em ≥2 meses"],
    ];
    els.kpis.innerHTML = cards.map((entry) =>
      `<div class="kpi"><div class="lbl">${entry[0]}</div><div class="val">${entry[1]}</div><div class="det">${entry[2]}</div></div>`
    ).join("");
  }

  function renderInsights(){
    const data = state.data;
    const bestCategory = data.categories[0];
    const worstCategory = data.categories[data.categories.length - 1];
    const topRiser = data.risers[0];
    const topFaller = data.fallers[0];
    const items = [
      ["Cobertura real", "O índice reflete " + fmt(data.kpis.coverage_pct, 1) + "% do gasto observado e rastreia " + data.kpis.tracked_products + " produtos."],
      ["Categoria mais rápida", bestCategory ? `${bestCategory.cat}: ${pct(bestCategory.ann_pct, 2)} ao ano.` : "–"],
      ["Categoria mais lenta", worstCategory ? `${worstCategory.cat}: ${pct(worstCategory.ann_pct, 2)} ao ano.` : "–"],
      ["Maior alta", topRiser ? `${topRiser.desc} foi de ${fmt(topRiser.p_first, 2)} para ${fmt(topRiser.p_last, 2)}.` : "–"],
      ["Maior queda", topFaller ? `${topFaller.desc} caiu de ${fmt(topFaller.p_first, 2)} para ${fmt(topFaller.p_last, 2)}.` : "–"],
    ];
    els.insights.innerHTML = items.map((item) =>
      `<div class="insight"><strong>${item[0]}</strong><span>${item[1]}</span></div>`
    ).join("");
  }

  function renderIndexChart(){
    const mount = els.chartIndex;
    mount.innerHTML = "";
    const pers = state.data.index;
    const ipca = state.data.ipca_ref;
    const months = pers.map((p) => p.m);
    const values = pers.map((p) => p.v).concat(ipca.map((p) => p.v));
    const W = 1000, H = 320, L = 42, R = 12, T = 12, B = 28;
    const ymin = Math.floor(Math.min(...values) / 10) * 10;
    const ymax = Math.ceil(Math.max(...values) / 10) * 10;
    const x = (i) => L + (W - L - R) * i / (months.length - 1);
    const y = (v) => T + (H - T - B) * (1 - (v - ymin) / (ymax - ymin));
    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, width: "100%"});

    for (let grid = ymin; grid <= ymax; grid += 10){
      svg.append(svgEl("line", {x1: L, x2: W - R, y1: y(grid), y2: y(grid), stroke: css("--grid"), "stroke-width": 1}));
      const label = svgEl("text", {x: L - 6, y: y(grid) + 4, "text-anchor": "end"});
      label.textContent = grid;
      svg.append(label);
    }

    let lastYear = null;
    months.forEach((month, i) => {
      if (month.endsWith("-01") || i === 0){
        const year = month.slice(0, 4);
        if (year !== lastYear){
          lastYear = year;
          const label = svgEl("text", {x: x(i), y: H - 8, "text-anchor": "middle"});
          label.textContent = year;
          svg.append(label);
        }
      }
    });

    const path = (series) => series.map((point, i) => (i ? "L" : "M") + x(i) + "," + y(point.v)).join("");
    svg.append(svgEl("path", {d: path(ipca), fill: "none", stroke: css("--ipca"), "stroke-width": 2, "stroke-dasharray": "5 4"}));
    svg.append(svgEl("path", {d: path(pers), fill: "none", stroke: css("--s1"), "stroke-width": 2.5, "stroke-linejoin": "round"}));

    const cross = svgEl("line", {y1: T, y2: H - B, stroke: css("--axis"), "stroke-width": 1, visibility: "hidden"});
    const dot = svgEl("circle", {r: 4, fill: css("--s1"), stroke: css("--surface"), "stroke-width": 2, visibility: "hidden"});
    svg.append(cross, dot);

    svg.addEventListener("mousemove", (event) => {
      const rect = svg.getBoundingClientRect();
      const px = (event.clientX - rect.left) * W / rect.width;
      let i = Math.round((px - L) / (W - L - R) * (months.length - 1));
      i = Math.max(0, Math.min(months.length - 1, i));
      cross.setAttribute("x1", x(i));
      cross.setAttribute("x2", x(i));
      cross.setAttribute("visibility", "visible");
      dot.setAttribute("cx", x(i));
      dot.setAttribute("cy", y(pers[i].v));
      dot.setAttribute("visibility", "visible");
      showTip(
        `<b>${mNice(months[i])}</b><br>Pessoal: <b>${fmt(pers[i].v, 1)}</b>` +
        (pers[i].n ? ` <span style="color:var(--muted)">(${pers[i].n} produtos)</span>` : "") +
        `<br>IPCA ref.: ${fmt(ipca[i].v, 1)}`,
        event.clientX,
        event.clientY
      );
    });
    svg.addEventListener("mouseleave", () => {
      hideTip();
      cross.setAttribute("visibility", "hidden");
      dot.setAttribute("visibility", "hidden");
    });

    const own = svgEl("text", {x: W - R - 2, y: y(pers[pers.length - 1].v) - 8, "text-anchor": "end", class: "dl"});
    own.textContent = "você " + fmt(pers[pers.length - 1].v, 0);
    own.style.fill = css("--s1");
    svg.append(own);

    const ref = svgEl("text", {x: W - R - 2, y: y(ipca[ipca.length - 1].v) + 14, "text-anchor": "end", class: "dl"});
    ref.textContent = "IPCA " + fmt(ipca[ipca.length - 1].v, 0);
    ref.style.fill = css("--ipca");
    svg.append(ref);

    mount.append(svg);
  }

  function renderYearChart(){
    const mount = els.chartYoy;
    mount.innerHTML = "";
    const rows = state.data.yoy;
    const W = 1000, H = 270, L = 44, R = 14, T = 16, B = 28;
    const values = rows.flatMap((row) => [row.personal, row.ipca == null ? 0 : row.ipca]);
    const ymax = Math.ceil(Math.max(...values, 0) / 2) * 2 + 2;
    const ymin = Math.min(0, Math.floor(Math.min(...values, 0) / 2) * 2);
    const y = (v) => T + (H - T - B) * (1 - (v - ymin) / (ymax - ymin));
    const groupW = (W - L - R) / rows.length;
    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, width: "100%"});

    for (let grid = ymin; grid <= ymax; grid += 2){
      svg.append(svgEl("line", {x1: L, x2: W - R, y1: y(grid), y2: y(grid), stroke: css("--grid")}));
      const label = svgEl("text", {x: L - 6, y: y(grid) + 4, "text-anchor": "end"});
      label.textContent = grid + "%";
      svg.append(label);
    }
    svg.append(svgEl("line", {x1: L, x2: W - R, y1: y(0), y2: y(0), stroke: css("--axis")}));

    rows.forEach((row, i) => {
      const cx = L + groupW * i + groupW / 2;
      const barW = Math.min(26, groupW / 3 - 4);
      [["personal", css("--s1"), -barW - 1, "Pessoal"], ["ipca", css("--ipca"), 1, "IPCA"]].forEach(([key, color, offset, label]) => {
        const value = row[key];
        if (value == null) return;
        const top = y(Math.max(0, value));
        const height = Math.max(Math.abs(y(value) - y(0)), 1);
        const bar = svgEl("rect", {x: cx + offset, y: top, width: barW, height, fill: color, rx: 3});
        bar.addEventListener("mousemove", (event) => showTip(
          `<b>${row.year}${row.partial ? " (parcial)" : ""}</b><br>${label}: <b>${pct(value, 2)}</b>`,
          event.clientX,
          event.clientY
        ));
        bar.addEventListener("mouseleave", hideTip);
        svg.append(bar);
      });
      const year = svgEl("text", {x: cx, y: H - 8, "text-anchor": "middle"});
      year.textContent = row.year + (row.partial ? "*" : "");
      svg.append(year);
      const value = svgEl("text", {x: cx - barW / 2 - 1, y: y(Math.max(0, row.personal)) - 5, "text-anchor": "middle", class: "dl"});
      value.textContent = fmt(row.personal, 1);
      value.style.fill = css("--s1");
      svg.append(value);
    });
    mount.append(svg);
    const partial = rows.find((row) => row.partial);
    if (partial){
      const note = document.createElement("p");
      note.className = "note";
      note.textContent = "* " + partial.year + ": ano incompleto (até " + mNice(state.data.kpis.last_month) + ").";
      mount.append(note);
    }
  }

  function renderCategoryChart(){
    const mount = els.chartCats;
    mount.innerHTML = "";
    const cats = state.data.categories;
    const W = 1000, rowH = 34, L = 150, R = 100;
    const H = cats.length * rowH + 10;
    const vmax = Math.max(...cats.map((row) => Math.abs(row.ann_pct)));
    const svg = svgEl("svg", {viewBox: `0 0 ${W} ${H}`, width: "100%"});
    const x0 = L;
    const xw = W - L - R;

    cats.forEach((row, i) => {
      const cy = i * rowH + rowH / 2 + 4;
      const width = xw * Math.abs(row.ann_pct) / vmax;
      const label = svgEl("text", {x: L - 8, y: cy + 4, "text-anchor": "end"});
      label.textContent = row.cat;
      label.style.fill = css("--ink2");
      svg.append(label);

      const bar = svgEl("rect", {
        x: x0, y: cy - 9, width: Math.max(width, 2), height: 18, rx: 4,
        fill: css("--s1"), opacity: 0.35 + 0.65 * (Math.abs(row.ann_pct) / vmax),
      });
      bar.addEventListener("mousemove", (event) => showTip(
        `<b>${row.cat}</b><br>${pct(row.ann_pct, 2)} ao ano · acumulado ${pct(row.cum_pct, 1)}` +
        `<br>${row.products} produtos · gasto ${brl(row.spend)}` +
        `<br><span style="color:var(--muted)">${mNice(row.from)} – ${mNice(row.to)}</span>`,
        event.clientX,
        event.clientY
      ));
      bar.addEventListener("mouseleave", hideTip);
      svg.append(bar);

      const value = svgEl("text", {x: x0 + Math.max(width, 2) + 8, y: cy + 4, class: "dl"});
      value.textContent = pct(row.ann_pct, 1) + " a.a.";
      value.style.fill = css("--ink");
      svg.append(value);
    });
    mount.append(svg);
  }

  function renderMoverTables(){
    function table(list){
      return `<table><thead><tr><th>Produto</th><th class="num">De</th><th class="num">Para</th><th class="num">%/ano</th></tr></thead><tbody>` +
        list.map((row) => `<tr><td title="${row.merchant}">${row.desc}</td><td class="num">${fmt(row.p_first, 2)}</td><td class="num">${fmt(row.p_last, 2)}</td><td class="num ${row.ann_pct >= 0 ? "pos" : "neg"}">${pct(row.ann_pct, 1)}</td></tr>`).join("") +
        `</tbody></table>`;
    }
    els.risers.innerHTML = table(state.data.risers);
    els.fallers.innerHTML = table(state.data.fallers);
  }

  function renderProductFilters(){
    const products = state.data.products;
    const rangeLabel = selectedRangeLabel();
    els.prodNote.textContent = products.length + " produtos comprados em pelo menos 2 meses, ordenados pelo gasto ou pela variação anualizada. Faixa ativa: " + rangeLabel + ".";

    const categories = ["all"].concat(Array.from(new Set(products.map((row) => row.cat))).sort());
    const merchants = ["all"].concat(Array.from(new Set(products.map((row) => row.merchant))).sort());
    const months = ["all"].concat(state.data.index.map((row) => row.m).filter((value, index, list) => list.indexOf(value) === index));
    hydrateSelect(els.categoryFilter, categories, state.category, "Todas as categorias");
    hydrateSelect(els.merchantFilter, merchants, state.merchant, "Todas as lojas");
    hydrateSelect(els.fromFilter, months, state.fromMonth, "Início do histórico");
    hydrateSelect(els.toFilter, months, state.toMonth, "Fim do histórico");
    els.search.value = state.query;
    els.sortFilter.value = state.sort;
  }

  function hydrateSelect(select, values, current, allLabel){
    select.innerHTML = values.map((value) => {
      const label = value === "all" ? allLabel : value;
      const selected = value === current ? " selected" : "";
      return `<option value="${escapeHtml(value)}"${selected}>${escapeHtml(label)}</option>`;
    }).join("");
  }

  function escapeHtml(value){
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function filteredProducts(){
    normalizeMonthRange();
    const fromMonth = state.fromMonth === "all" ? null : state.fromMonth;
    const toMonth = state.toMonth === "all" ? null : state.toMonth;
    const q = state.query.trim().toLowerCase();
    let rows = state.data.products.filter((row) => {
      if (state.category !== "all" && row.cat !== state.category) return false;
      if (state.merchant !== "all" && row.merchant !== state.merchant) return false;
      if (fromMonth && row.to < fromMonth) return false;
      if (toMonth && row.from > toMonth) return false;
      if (!q) return true;
      return (row.desc + " " + row.cat + " " + row.merchant).toLowerCase().includes(q);
    });

    const sorts = {
      "spend-desc": (a, b) => b.spend - a.spend,
      "ann-desc": (a, b) => (b.ann_pct ?? -Infinity) - (a.ann_pct ?? -Infinity),
      "ann-asc": (a, b) => (a.ann_pct ?? Infinity) - (b.ann_pct ?? Infinity),
      "months-desc": (a, b) => b.months - a.months || b.spend - a.spend,
    };
    rows = rows.slice().sort(sorts[state.sort] || sorts["spend-desc"]);
    return rows;
  }

  function renderProducts(){
    const rows = filteredProducts();
    els.resultsNote.textContent = rows.length + " produto(s) combinam com os filtros atuais em " + selectedRangeLabel() + ".";
    const visible = rows.slice(0, state.limit);
    els.prodBody.innerHTML = visible.map((row) => {
      const key = productKey(row);
      const selected = state.selectedProduct === key ? " class=\"is-selected\"" : "";
      return `<tr data-product-key="${escapeHtml(key)}"${selected}>
        <td title="${escapeHtml(row.merchant)}">${escapeHtml(row.desc)}</td>
        <td>${escapeHtml(row.cat)}</td>
        <td class="num">${row.months}</td>
        <td style="white-space:nowrap">${mNice(row.from)} – ${mNice(row.to)}</td>
        <td class="num">${fmt(row.p_first, 2)}</td>
        <td class="num">${fmt(row.p_last, 2)}</td>
        <td class="num ${row.cum_pct >= 0 ? "pos" : "neg"}">${pct(row.cum_pct, 1)}</td>
        <td class="num ${row.ann_pct >= 0 ? "pos" : "neg"}">${row.ann_pct == null ? "–" : pct(row.ann_pct, 1)}</td>
        <td class="num">${brl(row.spend)}</td>
      </tr>`;
    }).join("");
    els.moreBtn.style.display = rows.length > state.limit ? "" : "none";
    bindProductRows(rows);
    renderProductDetail(rows);
  }

  function productKey(row){
    return [row.desc, row.cat, row.merchant, row.from, row.to].join("¦");
  }

  function normalizeMonthRange(){
    if (state.fromMonth === "all" || state.toMonth === "all") return;
    if (state.fromMonth > state.toMonth){
      state.toMonth = state.fromMonth;
      if (els.toFilter) els.toFilter.value = state.toMonth;
    }
  }

  function selectedRangeLabel(){
    const first = state.data?.index?.[0]?.m;
    const last = state.data?.index?.[state.data.index.length - 1]?.m;
    const from = state.fromMonth === "all" ? first : state.fromMonth;
    const to = state.toMonth === "all" ? last : state.toMonth;
    if (!from || !to) return "todo o histórico";
    return mNice(from) + " – " + mNice(to);
  }

  function bindProductRows(rows){
    Array.from(els.prodBody.querySelectorAll("tr")).forEach((tr) => {
      tr.addEventListener("click", () => {
        state.selectedProduct = tr.dataset.productKey;
        renderProducts();
      });
    });
    if (!state.selectedProduct && rows[0]){
      state.selectedProduct = productKey(rows[0]);
    }
  }

  function renderProductDetail(rows){
    const selected = rows.find((row) => productKey(row) === state.selectedProduct);
    if (!selected){
      els.productDetail.className = "empty-state";
      els.productDetail.textContent = "Nenhum produto visível com os filtros atuais.";
      return;
    }
    els.productDetail.className = "detail-box";
    els.productDetail.innerHTML = `
      <h3>${escapeHtml(selected.desc)}</h3>
      <p>${escapeHtml(selected.merchant)}</p>
      <div class="detail-grid">
        <div><strong>Categoria</strong>${escapeHtml(selected.cat)}</div>
        <div><strong>Unidade</strong>${escapeHtml(selected.uom)}</div>
        <div><strong>Período</strong>${mNice(selected.from)} – ${mNice(selected.to)}</div>
        <div><strong>Meses observados</strong>${selected.months}</div>
        <div><strong>Primeiro preço</strong>${fmt(selected.p_first, 2)}</div>
        <div><strong>Último preço</strong>${fmt(selected.p_last, 2)}</div>
        <div><strong>Variação total</strong><span class="${selected.cum_pct >= 0 ? "pos" : "neg"}">${pct(selected.cum_pct, 1)}</span></div>
        <div><strong>Variação anualizada</strong><span class="${selected.ann_pct >= 0 ? "pos" : "neg"}">${pct(selected.ann_pct, 1)}</span></div>
        <div><strong>Gasto observado</strong>${brl(selected.spend)}</div>
      </div>`;
  }

  function renderValidation(){
    const report = state.validation;
    if (!report){
      els.validationKpis.innerHTML = "";
      els.validationSummary.innerHTML = '<div class="empty-state">Sem relatório de validação carregado.</div>';
      els.groundTruth.innerHTML = "";
      els.validationExamples.innerHTML = "";
      return;
    }

    const val = report.validation;
    const gt = report.ground_truth_check;

    const cards = [
      ["Duplicatas colapsadas", String(val.duplicate_xml_key_instances || 0), "re-downloads ou XMLs repetidos"],
      ["Canceladas excluídas", String(val.cancelled_unique_keys || 0), "chaves únicas CANC_*"],
      ["Campos numéricos ruins", String((val.malformed_numeric_fields || 0) + (val.missing_numeric_fields || 0)), "faltantes ou malformados"],
      ["Saltos >4x filtrados", String(val.filtered_large_jumps || 0), "troca de produto ou erro"],
      ["Produtos multi-unidade", String(val.products_with_multiple_units || 0), "separação UN vs KG preservada"],
    ];
    els.validationKpis.innerHTML = cards.map((entry) =>
      `<div class="kpi"><div class="lbl">${entry[0]}</div><div class="val">${entry[1]}</div><div class="det">${entry[2]}</div></div>`
    ).join("");

    const rows = [
      ["Pastas XML", String((val.xml_directories || []).length)],
      ["Arquivos XML lidos", String(val.xml_note_files || 0)],
      ["Chaves únicas", String(val.unique_xml_keys || 0)],
      ["Notas parseadas", String(val.parsed_receipts || 0)],
      ["Itens parseados", String(val.parsed_items || 0)],
      ["Receitas duplicadas puladas", String(val.duplicate_receipts_skipped || 0)],
      ["Receitas canceladas puladas", String(val.cancelled_receipts_skipped || 0)],
      ["EANs inválidos tratados", String(val.invalid_ean_fallbacks || 0)],
    ];
    els.validationSummary.innerHTML = rows.map((row) =>
      `<div class="stack-row"><span>${row[0]}</span><strong>${row[1]}</strong></div>`
    ).join("");

    if (gt.matches){
      els.groundTruth.innerHTML = `
        <p><span class="pill ok">OK</span></p>
        <p class="note">Os números atuais coincidem com a linha de base congelada do repositório.</p>
        <div class="stack-list">
          ${Object.keys(gt.actual).map((key) => `<div class="stack-row"><span>${key}</span><strong>${escapeHtml(String(gt.actual[key]))}</strong></div>`).join("")}
        </div>`;
    } else {
      els.groundTruth.innerHTML = `
        <p><span class="pill fail">FAIL</span></p>
        <div class="examples">
          ${gt.mismatches.map((row) => `<div class="example-block"><h3>${escapeHtml(row.metric)}</h3><pre>esperado: ${escapeHtml(String(row.expected))}\natual: ${escapeHtml(String(row.actual))}</pre></div>`).join("")}
        </div>`;
    }

    const exampleGroups = [
      ["Duplicatas", val.duplicate_xml_keys],
      ["EAN inválido", val.invalid_ean_examples],
      ["Campo numérico malformado", val.malformed_numeric_examples],
      ["Campo numérico ausente", val.missing_numeric_examples],
    ].filter((group) => Array.isArray(group[1]) && group[1].length);

    els.validationExamples.innerHTML = exampleGroups.length
      ? `<div class="examples">` + exampleGroups.map((group) =>
        `<div class="example-block"><h3>${group[0]}</h3><pre>${escapeHtml(JSON.stringify(group[1], null, 2))}</pre></div>`
      ).join("") + `</div>`
      : `<div class="empty-state">Nenhuma amostra de problema foi registrada nesta execução.</div>`;
  }

  els.navButtons.forEach((button) => {
    button.addEventListener("click", () => {
      state.view = button.dataset.view;
      renderNav();
    });
  });
  els.search.addEventListener("input", (event) => {
    state.query = event.target.value;
    state.limit = 40;
    renderProducts();
  });
  els.categoryFilter.addEventListener("change", (event) => {
    state.category = event.target.value;
    state.limit = 40;
    state.selectedProduct = null;
    renderProducts();
  });
  els.merchantFilter.addEventListener("change", (event) => {
    state.merchant = event.target.value;
    state.limit = 40;
    state.selectedProduct = null;
    renderProducts();
  });
  els.fromFilter.addEventListener("change", (event) => {
    state.fromMonth = event.target.value;
    state.limit = 40;
    state.selectedProduct = null;
    renderProducts();
  });
  els.toFilter.addEventListener("change", (event) => {
    state.toMonth = event.target.value;
    state.limit = 40;
    state.selectedProduct = null;
    renderProducts();
  });
  els.sortFilter.addEventListener("change", (event) => {
    state.sort = event.target.value;
    renderProducts();
  });
  els.moreBtn.addEventListener("click", () => {
    state.limit += 60;
    renderProducts();
  });

  boot();
})();
