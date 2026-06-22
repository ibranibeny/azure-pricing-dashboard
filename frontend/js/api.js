/* API client + formatting helpers. All data comes from the backend, which proxies the
   Azure Retail Prices API. "Not available" is rendered explicitly — never as 0 or blank. */
(function () {
  "use strict";

  var NA_TOKEN = "Not available";

  function qs(params) {
    var parts = [];
    Object.keys(params).forEach(function (k) {
      var v = params[k];
      if (v === undefined || v === null || v === "") return;
      parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(v));
    });
    return parts.length ? "?" + parts.join("&") : "";
  }

  async function getJson(url) {
    var res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) {
      var detail = "";
      try {
        var body = await res.json();
        detail = body.detail || body.warning || "";
      } catch (e) {
        /* ignore */
      }
      var err = new Error(detail || "Request failed (" + res.status + ")");
      err.status = res.status;
      throw err;
    }
    return res.json();
  }

  function fmtMoney(value, currency) {
    if (value === null || value === undefined) return null;
    // Azure unit prices are frequently sub-cent (e.g. $0.000243 per GiB/Hour, $0.0052 per 10K
    // operations). With a flat 2 decimals these collapse to "$0.00", so widen the precision for
    // small non-zero values while keeping normal amounts at 2 decimals.
    var abs = Math.abs(value);
    var maxFrac = 2;
    if (abs > 0 && abs < 1) maxFrac = abs < 0.01 ? 6 : 4;
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: currency || "USD",
        maximumFractionDigits: maxFrac,
        minimumFractionDigits: 2,
      }).format(value);
    } catch (e) {
      return (currency || "USD") + " " + Number(value).toFixed(maxFrac);
    }
  }

  /* Render a PricePoint cell: real money, or an explicit, honest "Not available". */
  function priceCell(point, currency) {
    if (point && point.available && point.price !== null && point.price !== undefined) {
      return { text: fmtMoney(point.price, currency), na: false };
    }
    return { text: NA_TOKEN, na: true };
  }

  function relativeTime(iso) {
    if (!iso) return "";
    var then = new Date(iso).getTime();
    if (isNaN(then)) return "";
    var mins = Math.max(0, Math.round((Date.now() - then) / 60000));
    if (mins < 1) return "just now";
    if (mins < 60) return mins + " min ago";
    var hrs = Math.round(mins / 60);
    if (hrs < 24) return hrs + " hr ago";
    return Math.round(hrs / 24) + " d ago";
  }

  window.Api = {
    NA_TOKEN: NA_TOKEN,
    listRegions: function (currency) {
      return getJson("/api/regions" + qs({ currencyCode: currency }));
    },
    regionOverview: function (region, currency) {
      return getJson(
        "/api/regions/" + encodeURIComponent(region) + "/services" + qs({ currencyCode: currency })
      );
    },
    pricing: function (params) {
      return getJson("/api/pricing" + qs(params));
    },
    exportUrl: function (fmt, params) {
      return "/api/export/" + fmt + qs(params);
    },
    fmtMoney: fmtMoney,
    priceCell: priceCell,
    relativeTime: relativeTime,
  };
})();
