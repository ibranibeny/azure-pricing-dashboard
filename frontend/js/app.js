/* Application controller: region-first browse -> service drill-down, with Hybrid Benefit toggles,
   honest staleness/provenance, export, and FinOps guidance. */
(function () {
  "use strict";

  // Service-first flow: choose a service, then a region, then prices. Indonesia Central is the
  // default region so step two is pre-filled, but nothing loads until a service is picked.
  var DEFAULT_REGION = "indonesiacentral";

  var state = {
    region: DEFAULT_REGION,
    currency: "USD",
    selected: null, // { serviceName, serviceFamily }
    rows: [], // current SKU rows for the selected service
    skuQuery: "", // per-service SKU filter text
    sortKey: "payg", // active sort column
    sortDir: "asc", // "asc" | "desc"; default shows lowest price first
    currencyCode: "USD",
    rateMode: "unit", // "hourly" (VMs/App Service) | "unit" (storage, bandwidth, ...)
    pageSize: 20, // number, or Infinity for "all"
    page: 0,
  };

  /* Default sort: cheapest pay-as-you-go SKU at the top. */
  var DEFAULT_SORT = { key: "payg", dir: "asc" };

  function el(id) {
    return document.getElementById(id);
  }

  function show(node, visible) {
    node.hidden = !visible;
  }

  /* ---- Provenance / freshness banner ---- */
  function setProvenance(meta) {
    var bar = el("provenance");
    if (!meta) {
      show(bar, false);
      return;
    }
    var badge = el("freshness-badge");
    if (meta.isStale) {
      badge.className = "badge badge--stale";
      badge.textContent = "Cached";
    } else {
      badge.className = "badge badge--live";
      badge.textContent = "Live";
    }
    el("source-line").textContent = "Source: " + (meta.source || "Azure Retail Prices API");
    el("retrieved-line").textContent = meta.retrievedAt
      ? "Retrieved " + window.Api.relativeTime(meta.retrievedAt)
      : "";
    setFooterDate(meta.retrievedAt);
    show(bar, true);
  }

  /* ---- Footer disclaimer date (absolute) ---- */
  function setFooterDate(iso) {
    var span = el("footer-data-date");
    if (!span) return;
    if (!iso) {
      span.textContent = "";
      return;
    }
    var d = new Date(iso);
    if (isNaN(d.getTime())) {
      span.textContent = "";
      return;
    }
    var date = d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
    var time = d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
    });
    span.textContent = " on " + date + " at " + time;
  }

  /* ---- Breadcrumb ---- */
  function setCrumbs(parts) {
    var nav = el("crumbs");
    nav.innerHTML = "";
    if (!parts || !parts.length) {
      show(nav, false);
      return;
    }
    parts.forEach(function (p, i) {
      if (i > 0) {
        var sep = document.createElement("span");
        sep.textContent = "/";
        nav.appendChild(sep);
      }
      if (p.onClick) {
        var b = document.createElement("button");
        b.type = "button";
        b.textContent = p.label;
        b.addEventListener("click", p.onClick);
        nav.appendChild(b);
      } else {
        var s = document.createElement("span");
        s.textContent = p.label;
        nav.appendChild(s);
      }
    });
    show(nav, true);
  }

  function overviewState(message) {
    var box = el("overview-state");
    box.innerHTML = "<p>" + message + "</p>";
    show(box, true);
  }

  /* ---- Views ---- */
  function showOverview() {
    state.selected = null;
    show(el("detail-view"), false);
    show(el("overview-view"), true);
    setCrumbs(null);
    renderDirectory();
  }

  /* Render the service directory (no API call), filtered by the search box. */
  function renderDirectory() {
    var term = el("service-search").value;
    var grid = el("service-grid");
    var shown = window.Overview.render(grid, term, selectService);
    show(grid, shown > 0);
    if (shown > 0) {
      show(el("overview-state"), false);
    } else {
      overviewState('No services match \u201c' + esc(term.trim()) + '\u201d. Try a shorter term.');
    }
  }

  async function loadRegions() {
    try {
      var regions = await window.Api.listRegions(state.currency);
      var sel = el("region-select");
      sel.innerHTML = "";
      var placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Select a region…";
      sel.appendChild(placeholder);
      regions.forEach(function (r) {
        var opt = document.createElement("option");
        opt.value = r.armRegionName;
        opt.textContent = (r.location || r.armRegionName) + " (" + r.armRegionName + ")";
        sel.appendChild(opt);
      });
      // Reflect the default region in the picker once options exist.
      if (state.region) sel.value = state.region;
    } catch (e) {
      // Regions come from a cheap probe; if it fails, the directory still works and the
      // pricing query will surface the upstream error honestly.
      var sel2 = el("region-select");
      sel2.innerHTML = '<option value="' + esc(state.region) + '">' + esc(state.region) + "</option>";
    }
  }

  async function loadOverview() {
    // Retained for symmetry with the old region-first flow; the directory needs no fetch.
    renderDirectory();
    setProvenance(null);
  }

  /* ---- Drill-down ---- */
  function currentParams() {
    if (!state.selected) return null;
    var hb = window.Filters.get();
    return {
      serviceName: state.selected.serviceName,
      armRegionName: state.region,
      currencyCode: state.currency,
      windowsHybridBenefit: hb.windowsHybridBenefit,
      sqlHybridBenefit: hb.sqlHybridBenefit,
    };
  }

  function selectService(service) {
    state.selected = service;
    state.page = 0;
    state.skuQuery = "";
    state.sortKey = DEFAULT_SORT.key;
    state.sortDir = DEFAULT_SORT.dir;
    window.Filters.reset();
    el("service-search").value = "";
    if (el("sku-search")) el("sku-search").value = "";
    show(el("sku-filter"), false);
    show(el("overview-view"), false);
    show(el("detail-view"), true);
    el("detail-title").textContent = service.serviceName + " — " + state.region;
    setCrumbs([
      { label: "All services", onClick: showOverview },
      { label: service.serviceFamily || "Service" },
      { label: service.serviceName },
    ]);
    loadDetail();
  }

  /* Escape user/API-sourced strings before they touch innerHTML (defense in depth). */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* Treat every VM SKU as on-demand: drop the "Spot" marker from displayed names. */
  function cleanSku(s) {
    return String(s == null ? "" : s).replace(/\s*\bspot\b/gi, "").trim();
  }

  /* Azure returns reserved prices as the full-term total; convert to an effective
     hourly rate so the saving compares like-for-like against pay-as-you-go. */
  var TERM_HOURS = { "1-yr": 8760, "3-yr": 26280 };

  function isHourly(point) {
    return !!(point && point.unitOfMeasure && /hour/i.test(point.unitOfMeasure));
  }

  /* A service is shown either per-hour (VMs, App Service, AKS — every PAYG meter is hourly)
     or per its own native unit (Storage operations, GB/Month, bandwidth ...). The price
     columns and headers adapt to whichever basis the service actually bills on. */
  function computeRateMode(rows) {
    var any = false;
    var allHourly = true;
    rows.forEach(function (r) {
      if (r.payg && r.payg.available && r.payg.price != null) {
        any = true;
        if (!isHourly(r.payg)) allHourly = false;
      }
    });
    return any && allHourly ? "hourly" : "unit";
  }

  /* Amount to display for a price column, on the service's rate basis:
       - hourly mode: PAYG is already per hour; reserved prices are full-term totals, so
         divide across the term's hours to get the effective hourly rate;
       - unit mode: show each meter's raw price in its own native unit (the Unit column
         spells out the unit), so we never force a misleading monthly figure. */
  function displayAmount(point, kind, mode) {
    if (!point || !point.available || point.price == null) return null;
    mode = mode || state.rateMode || "unit";
    if (mode === "hourly") {
      if (kind === "1y") return point.price / TERM_HOURS["1-yr"];
      if (kind === "3y") return point.price / TERM_HOURS["3-yr"];
      return point.price;
    }
    return point.price;
  }

  /* priceCell-style result ({ text, na }) for a column on the service's rate basis. */
  function displayCell(point, currency, kind, mode) {
    var v = displayAmount(point, kind, mode);
    if (v == null) return { text: window.Api.NA_TOKEN, na: true };
    return { text: window.Api.fmtMoney(v, currency), na: false };
  }

  /* Retitle the price columns to match the active rate basis (per-hour vs native unit). */
  function updateRateHeaders(mode) {
    var suffix = mode === "hourly" ? " / hr" : "";
    var labels = {
      payg: "Pay-as-you-go",
      reserved1Y: "1-year reserved",
      reserved3Y: "3-year reserved",
    };
    Object.keys(labels).forEach(function (key) {
      var btn = document.querySelector('.th-sort[data-sort="' + key + '"]');
      if (btn && btn.firstChild) btn.firstChild.nodeValue = labels[key] + suffix;
    });
  }

  /* Honest reserved saving for ONE term vs the SKU's hourly pay-as-you-go rate. */
  function savingForTerm(row, term) {
    var paygPt = row.payg && row.payg.available ? row.payg : null;
    if (!paygPt || paygPt.price == null || paygPt.price <= 0 || !isHourly(paygPt)) return null;
    var res = term === "1-yr" ? row.reserved1Y : row.reserved3Y;
    if (!res || !res.available || res.price == null) return null;
    var effective = res.price / TERM_HOURS[term];
    var pct = (paygPt.price - effective) / paygPt.price;
    if (pct <= 0 || pct >= 1) return null;
    return { pct: pct, term: term, effective: effective, total: res.price };
  }

  /* Best reserved saving across terms (3-yr preferred when it matches or beats 1-yr). */
  function bestReserved(row) {
    var one = savingForTerm(row, "1-yr");
    var three = savingForTerm(row, "3-yr");
    if (three && (!one || three.pct >= one.pct)) return three;
    return one || three;
  }

  /* KPI meter rail: SKUs priced, lowest PAYG, best reserved saving, reserved coverage. */
  function renderKpis(rows, currency) {
    var rail = el("kpi-rail");
    rail.innerHTML = "";
    var paygs = [];
    var best = null;
    var bestTerm = "";
    var reservedCount = 0;
    rows.forEach(function (r) {
      // Skip free meters (e.g. Delete Operations, "Provisioned IOPS Free") so the headline
      // reflects the lowest *billable* price instead of collapsing to $0.00.
      if (r.payg && r.payg.available && r.payg.price != null && r.payg.price > 0) {
        paygs.push(r.payg.price);
      }
      if ((r.reserved1Y && r.reserved1Y.available) || (r.reserved3Y && r.reserved3Y.available)) {
        reservedCount++;
      }
      var s = bestReserved(r);
      if (s && (best === null || s.pct > best)) {
        best = s.pct;
        bestTerm = s.term;
      }
    });
    var lowest = paygs.length ? Math.min.apply(null, paygs) : null;
    var tiles = [
      { label: "SKUs priced", value: String(rows.length) },
      {
        label: "Lowest pay-as-you-go",
        value: lowest != null ? window.Api.fmtMoney(lowest, currency) : window.Api.NA_TOKEN,
      },
      {
        label: "Best reserved saving",
        value: best != null ? "-" + Math.round(best * 100) + "%" : "\u2014",
        sub: best != null ? bestTerm + " commitment" : "no reserved pricing",
        save: true,
      },
      { label: "SKUs with reserved pricing", value: String(reservedCount) },
    ];
    tiles.forEach(function (t) {
      var card = document.createElement("div");
      card.className = "kpi" + (t.save ? " kpi--save" : "");
      var lab = document.createElement("span");
      lab.className = "kpi__label";
      lab.textContent = t.label;
      var val = document.createElement("span");
      val.className = "kpi__value";
      val.textContent = t.value;
      card.appendChild(lab);
      card.appendChild(val);
      if (t.sub) {
        var sub = document.createElement("span");
        sub.className = "kpi__sub";
        sub.textContent = t.sub;
        card.appendChild(sub);
      }
      rail.appendChild(card);
    });
    show(rail, rows.length > 0);
  }

  /* One compact gauge for a single term. Renders the meter + label, or an em dash. */
  function gaugeHtml(saving, term) {
    if (!saving) {
      return '<span class="dual__cell"><span class="dual__term">' + term + '</span><span class="na">\u2014</span></span>';
    }
    var pct = Math.round(saving.pct * 100);
    return (
      '<span class="dual__cell">' +
      '<span class="dual__term">' + term + '</span>' +
      '<span class="gauge gauge--mini"><span class="gauge__fill" style="width:' +
      Math.min(100, pct) +
      '%"></span></span>' +
      '<span class="dual__pct mono">-' + pct + "%</span>" +
      "</span>"
    );
  }

  /* Rows visible after the per-service SKU filter (search box above the ledger). */
  function visibleRows() {
    var q = state.skuQuery.trim().toLowerCase();
    if (!q) return state.rows;
    return state.rows.filter(function (r) {
      var hay = [r.skuName, r.armSkuName, r.meterName, r.productName, r.unitOfMeasure]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.indexOf(q) !== -1;
    });
  }

  /* Comparable value for a row under a given sort key.
     Returns { v, missing } so unavailable prices always sink to the bottom. */
  function sortValue(row, key) {
    switch (key) {
      case "sku":
        return { v: (row.armSkuName || row.skuName || "").toLowerCase(), missing: false };
      case "unit":
        return { v: (row.unitOfMeasure || "").toLowerCase(), missing: false };
      case "payg":
        return priceSortValue(displayAmount(row.payg, "payg"), true);
      case "reserved1Y":
        return priceSortValue(displayAmount(row.reserved1Y, "1y"));
      case "reserved3Y":
        return priceSortValue(displayAmount(row.reserved3Y, "3y"));
      case "saves": {
        var best = bestReserved(row);
        return best ? { v: best.pct, missing: false } : { v: 0, missing: true };
      }
      default:
        return { v: 0, missing: true };
    }
  }

  function priceSortValue(amount, sinkZero) {
    if (amount !== null && amount !== undefined) {
      // For pay-as-you-go, treat free ($0) meters like missing values so they sink below the
      // real prices instead of dominating the top of an ascending sort.
      if (sinkZero && amount === 0) return { v: 0, missing: true };
      return { v: amount, missing: false };
    }
    return { v: 0, missing: true };
  }

  /* Rows after filtering, sorted by the active column. Missing values always last. */
  function sortedRows() {
    var rows = visibleRows().slice();
    var key = state.sortKey;
    var dir = state.sortDir === "desc" ? -1 : 1;
    rows.sort(function (a, b) {
      var av = sortValue(a, key);
      var bv = sortValue(b, key);
      if (av.missing !== bv.missing) return av.missing ? 1 : -1;
      if (av.missing && bv.missing) return 0;
      if (av.v < bv.v) return -1 * dir;
      if (av.v > bv.v) return 1 * dir;
      return 0;
    });
    return rows;
  }

  /* Slice of rows for the current page, honoring "show all". */
  function pageRows() {
    var rows = sortedRows();
    if (state.pageSize === Infinity) return rows;
    var start = state.page * state.pageSize;
    return rows.slice(start, start + state.pageSize);
  }

  function totalPages() {
    if (state.pageSize === Infinity) return 1;
    return Math.max(1, Math.ceil(visibleRows().length / state.pageSize));
  }

  function renderLedger(rows, currency, showHb) {
    var body = el("ledger-body");
    body.innerHTML = "";
    document.querySelectorAll(".hb-col").forEach(function (c) {
      c.hidden = !showHb;
    });

    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      tr.className = "ledger-row";
      tr.tabIndex = 0;
      tr.setAttribute("role", "button");
      tr.setAttribute("aria-label", "Show pricing detail for " + (row.armSkuName || "this SKU"));

      var sku = document.createElement("td");
      // VMs have an armSkuName; multi-dimensional services (storage, bandwidth, ...) don't, so
      // lead with the SKU name and show the specific meter (Read Operations, Data Stored, ...).
      var primary = row.armSkuName || row.skuName || row.meterName || "";
      var secondary;
      if (row.armSkuName) {
        secondary = row.skuName || "";
      } else {
        // Multi-dimensional services can expose the same skuName + meterName under different
        // product variants (e.g. Azure Files "Files" vs "Files v2"). Append the product so those
        // rows are distinguishable instead of looking like duplicates.
        var parts = [];
        if (row.meterName) parts.push(cleanSku(row.meterName));
        if (row.productName && row.productName !== row.skuName) parts.push(cleanSku(row.productName));
        secondary = parts.join(" · ");
      }
      sku.innerHTML =
        "<strong>" + esc(cleanSku(primary)) + "</strong><br><small>" + esc(secondary) + "</small>";
      tr.appendChild(sku);

      var unit = document.createElement("td");
      unit.textContent = row.unitOfMeasure || "";
      tr.appendChild(unit);

      [
        { pt: row.payg, kind: "payg" },
        { pt: row.reserved1Y, kind: "1y" },
        { pt: row.reserved3Y, kind: "3y" },
      ].forEach(function (spec) {
        var td = document.createElement("td");
        td.className = "price";
        var cell = displayCell(spec.pt, currency, spec.kind);
        if (cell.na) {
          td.innerHTML = '<span class="na">' + cell.text + "</span>";
        } else {
          td.textContent = cell.text;
        }
        tr.appendChild(td);
      });

      // Reserved saves: 1-year and 3-year side by side so the commitment trade-off is visible.
      var sv = document.createElement("td");
      sv.className = "savings";
      sv.innerHTML =
        '<div class="dual">' +
        gaugeHtml(savingForTerm(row, "1-yr"), "1y") +
        gaugeHtml(savingForTerm(row, "3-yr"), "3y") +
        "</div>";
      tr.appendChild(sv);

      if (showHb) {
        var hbTd = document.createElement("td");
        hbTd.className = "price hb-col";
        var hb = row.hybridBenefit;
        if (hb && hb.eligiblePrice !== null && hb.eligiblePrice !== undefined) {
          hbTd.textContent = window.Api.fmtMoney(hb.eligiblePrice, currency);
        } else {
          hbTd.innerHTML = '<span class="na">' + window.Api.NA_TOKEN + "</span>";
        }
        tr.appendChild(hbTd);
      }

      tr.addEventListener("click", function () {
        openDrawer(row, currency);
      });
      tr.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openDrawer(row, currency);
        }
      });

      body.appendChild(tr);
    });
  }

  /* Pager footer: row count, page-size selector (incl. custom + all), and prev/next. */
  function renderPager() {
    var pager = el("ledger-pager");
    var total = visibleRows().length;
    if (!total) {
      show(pager, false);
      return;
    }
    show(pager, true);

    var pages = totalPages();
    if (state.page >= pages) state.page = pages - 1;

    var countEl = el("pager-count");
    if (state.pageSize === Infinity) {
      countEl.textContent = total + " SKU" + (total === 1 ? "" : "s");
    } else {
      var first = state.page * state.pageSize + 1;
      var last = Math.min(total, first + state.pageSize - 1);
      countEl.textContent = first + "\u2013" + last + " of " + total + " SKUs";
    }

    el("pager-pos").textContent = "Page " + (state.page + 1) + " / " + pages;
    el("page-prev").disabled = state.page <= 0;
    el("page-next").disabled = state.page >= pages - 1;
  }

  /* Update the "N of M SKUs" readout next to the per-service filter. */
  function renderSkuMatchCount() {
    var countEl = el("sku-match-count");
    if (!countEl) return;
    var total = state.rows.length;
    var shown = visibleRows().length;
    if (!state.skuQuery.trim()) {
      countEl.textContent = total + " SKU" + (total === 1 ? "" : "s");
    } else {
      countEl.textContent = shown + " of " + total + " SKUs";
    }
  }

  /* Re-render just the table body + pager for the current page (no refetch). */
  function repaginate() {
    var rows = pageRows();
    if (!rows.length && state.skuQuery.trim()) {
      var body = el("ledger-body");
      body.innerHTML =
        '<tr><td class="ledger-empty" colspan="7">No SKUs match \u201c' +
        esc(state.skuQuery.trim()) +
        '\u201d. Try a shorter term.</td></tr>';
    } else {
      renderLedger(rows, state.currencyCode, window.Filters.anyOn());
    }
    renderPager();
    renderSkuMatchCount();
    renderSortIndicators();
  }

  /* Reflect the active sort column/direction on the header buttons (arrow + aria-sort). */
  function renderSortIndicators() {
    var head = el("ledger-head");
    if (!head) return;
    head.querySelectorAll(".th-sort").forEach(function (btn) {
      var key = btn.getAttribute("data-sort");
      var th = btn.closest("th");
      var ind = btn.querySelector(".th-sort__ind");
      if (key === state.sortKey) {
        btn.classList.add("is-active");
        var asc = state.sortDir === "asc";
        if (ind) ind.textContent = asc ? "\u2191" : "\u2193";
        if (th) th.setAttribute("aria-sort", asc ? "ascending" : "descending");
      } else {
        btn.classList.remove("is-active");
        if (ind) ind.textContent = "";
        if (th) th.removeAttribute("aria-sort");
      }
    });
  }

  /* ---- SKU detail drawer ---- */
  function priceLine(label, pt, currency, note) {
    var cell = window.Api.priceCell(pt, currency);
    var value = cell.na
      ? '<span class="na">' + cell.text + "</span>"
      : '<span class="mono">' + esc(cell.text) + "</span>";
    var sub = note ? '<span class="drawer__note">' + esc(note) + "</span>" : "";
    return (
      '<div class="drawer__row"><span class="drawer__key">' +
      esc(label) +
      "</span><span class=\"drawer__val\">" +
      value +
      sub +
      "</span></div>"
    );
  }

  /* Drawer pricing row showing the cost for a column on the service's rate basis. */
  function displayPriceLine(label, pt, currency, kind, note) {
    var cell = displayCell(pt, currency, kind);
    var value = cell.na
      ? '<span class="na">' + cell.text + "</span>"
      : '<span class="mono">' + esc(cell.text) + "</span>";
    var sub = note ? '<span class="drawer__note">' + esc(note) + "</span>" : "";
    return (
      '<div class="drawer__row"><span class="drawer__key">' +
      esc(label) +
      "</span><span class=\"drawer__val\">" +
      value +
      sub +
      "</span></div>"
    );
  }

  function openDrawer(row, currency) {
    var eyebrow = el("drawer-eyebrow");
    var title = el("drawer-title");
    var bodyEl = el("drawer-body");
    eyebrow.textContent = (state.selected ? state.selected.serviceName : "") + " · " + state.region;
    title.textContent = cleanSku(row.armSkuName || row.skuName || "SKU detail");

    var one = savingForTerm(row, "1-yr");
    var three = savingForTerm(row, "3-yr");
    var html = "";

    html += '<div class="drawer__section">';
    html += '<h3 class="drawer__h">Identity</h3>';
    html += priceLineText("SKU name", cleanSku(row.skuName || row.armSkuName));
    if (row.productName) html += priceLineText("Product", row.productName);
    html += priceLineText("Service", row.serviceName + " · " + (row.serviceFamily || ""));
    html += priceLineText("Region", (row.location || "") + " (" + (row.armRegionName || state.region) + ")");
    html += priceLineText("Billed per", row.unitOfMeasure || "");
    html += "</div>";

    html += '<div class="drawer__section">';
    html += '<h3 class="drawer__h">Pricing</h3>';
    var rateSuffix = state.rateMode === "hourly" ? " / hr" : " / " + (row.unitOfMeasure || "unit");
    html += displayPriceLine("Pay-as-you-go" + rateSuffix, row.payg, currency, "payg", null);
    html += displayPriceLine(
      "1-year reserved" + rateSuffix,
      row.reserved1Y,
      currency,
      "1y",
      one ? "\u2248 " + window.Api.fmtMoney(one.effective, currency) + " / hr effective" : null
    );
    html += displayPriceLine(
      "3-year reserved" + rateSuffix,
      row.reserved3Y,
      currency,
      "3y",
      three ? "\u2248 " + window.Api.fmtMoney(three.effective, currency) + " / hr effective" : null
    );
    if (row.hybridBenefit && row.hybridBenefit.eligiblePrice != null) {
      html += priceLineText("Hybrid Benefit price", window.Api.fmtMoney(row.hybridBenefit.eligiblePrice, currency));
    }
    html += "</div>";

    html += '<div class="drawer__section">';
    html += '<h3 class="drawer__h">Reserved savings</h3>';
    html += savingRow("1-year commitment", one);
    html += savingRow("3-year commitment", three);
    if (!one && !three) {
      html += '<p class="drawer__empty">No reserved pricing is published for this SKU, so there\u2019s nothing to compare against pay-as-you-go.</p>';
    }
    html += "</div>";

    bodyEl.innerHTML = html;
    show(el("drawer-backdrop"), true);
    show(el("sku-drawer"), true);
    document.body.classList.add("drawer-open");
    el("drawer-close").focus();
  }

  function priceLineText(label, value) {
    return (
      '<div class="drawer__row"><span class="drawer__key">' +
      esc(label) +
      '</span><span class="drawer__val">' +
      esc(value || "") +
      "</span></div>"
    );
  }

  function savingRow(label, saving) {
    if (!saving) {
      return (
        '<div class="drawer__row"><span class="drawer__key">' +
        esc(label) +
        '</span><span class="drawer__val"><span class="na">\u2014</span></span></div>'
      );
    }
    var pct = Math.round(saving.pct * 100);
    return (
      '<div class="drawer__saving">' +
      '<div class="drawer__saving-head"><span class="drawer__key">' +
      esc(label) +
      '</span><span class="dual__pct mono">-' +
      pct +
      "%</span></div>" +
      '<span class="gauge"><span class="gauge__fill" style="width:' +
      Math.min(100, pct) +
      '%"></span></span></div>'
    );
  }

  function closeDrawer() {
    show(el("sku-drawer"), false);
    show(el("drawer-backdrop"), false);
    document.body.classList.remove("drawer-open");
  }

  function renderGuidance(items) {
    var box = el("guidance");
    var list = el("guidance-list");
    list.innerHTML = "";
    if (!items || !items.length) {
      show(box, false);
      return;
    }
    items.forEach(function (text) {
      var li = document.createElement("li");
      li.textContent = text;
      list.appendChild(li);
    });
    show(box, true);
  }

  async function loadDetail() {
    var params = currentParams();
    if (!params) return;
    show(el("detail-state"), true);
    show(el("ledger-wrap"), false);
    show(el("ledger-pager"), false);
    show(el("sku-filter"), false);
    show(el("guidance"), false);
    show(el("kpi-rail"), false);
    el("detail-title").textContent = state.selected.serviceName + " \u2014 " + state.region;
    try {
      var data = await window.Api.pricing(params);
      setProvenance({ isStale: data.isStale, source: data.source, retrievedAt: data.retrievedAt });
      show(el("detail-state"), false);
      if (!data.rows.length) {
        el("detail-state").innerHTML =
          '<p class="error">' +
          esc(data.warning || "No meters are published for this service in " + state.region + ". Try another region, or pick a different service.") +
          "</p>";
        show(el("detail-state"), true);
        return;
      }
      state.rows = data.rows;
      state.currencyCode = data.currencyCode;
      state.rateMode = computeRateMode(data.rows);
      state.page = 0;
      updateRateHeaders(state.rateMode);
      renderKpis(data.rows, data.currencyCode);
      repaginate();
      show(el("sku-filter"), true);
      show(el("ledger-wrap"), true);
      renderGuidance(data.guidance);
    } catch (e) {
      el("detail-state").innerHTML = '<p class="error">Could not load prices: ' + esc(e.message) + "</p>";
      show(el("detail-state"), true);
    }
  }

  /* ---- Wiring ---- */
  function applyPageSize(raw) {
    if (raw === "all") {
      state.pageSize = Infinity;
    } else {
      var n = parseInt(raw, 10);
      state.pageSize = isNaN(n) || n < 1 ? 20 : n;
    }
    state.page = 0;
    if (state.selected && state.rows.length) repaginate();
  }

  function init() {
    el("region-select").addEventListener("change", function (e) {
      state.region = e.target.value;
      // Keep viewing the same service when the region changes; otherwise stay on the directory.
      if (state.selected) selectService(state.selected);
    });
    el("currency-select").addEventListener("change", function (e) {
      state.currency = e.target.value;
      if (state.selected) loadDetail();
    });
    el("service-search").addEventListener("input", function () {
      // Typing always returns to the directory so you can switch services.
      if (state.selected) showOverview();
      else renderDirectory();
    });
    el("sku-search").addEventListener("input", function (e) {
      // Filter the open service's SKUs in place; no refetch, just re-page.
      state.skuQuery = e.target.value;
      state.page = 0;
      repaginate();
    });
    el("ledger-head").addEventListener("click", function (e) {
      var btn = e.target.closest(".th-sort");
      if (!btn) return;
      var key = btn.getAttribute("data-sort");
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        // Text columns read best A→Z; price/savings columns lead with the lowest.
        state.sortDir = "asc";
      }
      state.page = 0;
      repaginate();
    });
    window.Filters.onChange(function () {
      if (state.selected) loadDetail();
    });
    window.Exporter.bind(currentParams);

    // Paging controls.
    el("page-size").addEventListener("change", function (e) {
      var v = e.target.value;
      var custom = el("page-size-custom");
      if (v === "custom") {
        show(custom, true);
        custom.focus();
        if (custom.value) applyPageSize(custom.value);
      } else {
        show(custom, false);
        applyPageSize(v);
      }
    });
    el("page-size-custom").addEventListener("input", function (e) {
      if (e.target.value) applyPageSize(e.target.value);
    });
    el("page-prev").addEventListener("click", function () {
      if (state.page > 0) {
        state.page--;
        repaginate();
        el("ledger-wrap").scrollIntoView({ block: "start", behavior: "smooth" });
      }
    });
    el("page-next").addEventListener("click", function () {
      if (state.page < totalPages() - 1) {
        state.page++;
        repaginate();
        el("ledger-wrap").scrollIntoView({ block: "start", behavior: "smooth" });
      }
    });

    // Drawer dismissal.
    el("drawer-close").addEventListener("click", closeDrawer);
    el("drawer-backdrop").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !el("sku-drawer").hidden) closeDrawer();
    });

    loadRegions();
    // Service-first: open on the directory. Nothing is fetched until a service is chosen.
    showOverview();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
