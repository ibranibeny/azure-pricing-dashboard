/* Export buttons (US3): download the exact current comparison as CSV or XLSX. The backend builds
   the file from the same rows shown on screen, so the file can never diverge from the view. */
(function () {
  "use strict";

  function trigger(url) {
    var a = document.createElement("a");
    a.href = url;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  window.Exporter = {
    bind: function (getParams) {
      document.getElementById("export-csv").addEventListener("click", function () {
        var p = getParams();
        if (p) trigger(window.Api.exportUrl("csv", p));
      });
      document.getElementById("export-xlsx").addEventListener("click", function () {
        var p = getParams();
        if (p) trigger(window.Api.exportUrl("xlsx", p));
      });
    },
  };
})();
