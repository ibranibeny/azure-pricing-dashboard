/* Service directory (landing): pick a service first, then a region, then see prices. Grouped by the
   Azure service family taxonomy — the family eyebrow encodes a real grouping, not decoration.
   No prices here; selecting a service runs one narrow pricing query for the chosen region. */
(function () {
  "use strict";

  function serviceButton(svc, onSelect) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "svc";
    btn.setAttribute("aria-label", "Price " + svc.serviceName);

    var name = document.createElement("span");
    name.className = "svc__name";
    name.textContent = svc.serviceName;
    btn.appendChild(name);

    var meta = document.createElement("span");
    meta.className = "svc__meta";
    meta.textContent = svc.perSku ? "Priced per SKU" : "View meters";
    btn.appendChild(meta);

    btn.addEventListener("click", function () {
      onSelect({ serviceName: svc.serviceName, serviceFamily: svc.serviceFamily });
    });
    return btn;
  }

  /* Render the whole directory, optionally filtered by a search term over service names.
     Returns how many services are visible so the caller can show an empty state. */
  function render(container, term, onSelect) {
    container.innerHTML = "";
    var q = (term || "").trim().toLowerCase();
    var shown = 0;

    window.ServiceCatalog.families.forEach(function (group) {
      var matches = group.services.filter(function (name) {
        return !q || name.toLowerCase().indexOf(q) !== -1;
      });
      if (!matches.length) return;
      shown += matches.length;

      var section = document.createElement("section");
      section.className = "svc-group";

      var head = document.createElement("div");
      head.className = "svc-group__head";
      var eyebrow = document.createElement("span");
      eyebrow.className = "svc-group__family";
      eyebrow.textContent = group.family;
      var blurb = document.createElement("span");
      blurb.className = "svc-group__blurb";
      blurb.textContent = group.blurb;
      head.appendChild(eyebrow);
      head.appendChild(blurb);
      section.appendChild(head);

      var grid = document.createElement("div");
      grid.className = "svc-grid";
      matches.forEach(function (name) {
        grid.appendChild(
          serviceButton(
            {
              serviceName: name,
              serviceFamily: group.family,
              perSku: !!window.ServiceCatalog.perSku[name],
            },
            onSelect
          )
        );
      });
      section.appendChild(grid);
      container.appendChild(section);
    });

    return shown;
  }

  window.Overview = { render: render };
})();
