/* Hybrid Benefit toggles (US2): Windows Server and SQL Server apply independently. */
(function () {
  "use strict";

  function el(id) {
    return document.getElementById(id);
  }

  window.Filters = {
    get: function () {
      return {
        windowsHybridBenefit: el("toggle-windows").checked,
        sqlHybridBenefit: el("toggle-sql").checked,
      };
    },
    onChange: function (cb) {
      el("toggle-windows").addEventListener("change", cb);
      el("toggle-sql").addEventListener("change", cb);
    },
    reset: function () {
      el("toggle-windows").checked = false;
      el("toggle-sql").checked = false;
    },
    anyOn: function () {
      return el("toggle-windows").checked || el("toggle-sql").checked;
    },
  };
})();
