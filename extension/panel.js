/*
 * panel.js -- the draggable in-page panel. Pure DOM, no framework.
 * Modelled on the reference panel: a drag handle, a collapse toggle, a status
 * line, a stats block and real <button> elements (keyboard-accessible, in tab
 * order). content.js owns the logic and registers handlers via PlePanel.on().
 */
(function (global) {
  "use strict";

  // May be injected twice (registered content script + popup inject-now). Keep
  // the first instance so its handlers stay bound to the DOM buttons.
  if (global.PlePanel) return;

  var els = null;
  var handlers = { scan: null, exportCsv: null, exportXlsx: null, clear: null };

  function build() {
    if (document.getElementById("ple-panel")) return;

    var panel = document.createElement("div");
    panel.id = "ple-panel";
    panel.setAttribute("role", "region");
    panel.setAttribute("aria-label", "Property Listing Collector");
    panel.innerHTML =
      '<div class="ple-header" id="ple-header">' +
      '  <span class="ple-title">Listing Collector</span>' +
      '  <button type="button" class="ple-toggle" id="ple-toggle" aria-label="Collapse or expand">&#8211;</button>' +
      "</div>" +
      '<div class="ple-body">' +
      '  <div class="ple-stats">' +
      "    <span>On this page</span><span class=\"ple-num\" id=\"ple-page\">0</span>" +
      "    <span>Collected (unique)</span><span class=\"ple-num\" id=\"ple-unique\">0</span>" +
      "    <span>Duplicates skipped</span><span class=\"ple-num\" id=\"ple-dupes\">0</span>" +
      "  </div>" +
      '  <div class="ple-status" id="ple-status" role="status" aria-live="polite">Ready.</div>' +
      '  <div class="ple-buttons">' +
      '    <button type="button" class="ple-btn ple-btn-primary" id="ple-scan">Scan this page</button>' +
      '    <button type="button" class="ple-btn" id="ple-csv">Export CSV</button>' +
      '    <button type="button" class="ple-btn" id="ple-xlsx">Export XLSX</button>' +
      '    <button type="button" class="ple-btn" id="ple-clear">Clear</button>' +
      "  </div>" +
      '  <div class="ple-footnote">Reads the page’s own embedded JSON. No auto-navigation — you drive.</div>' +
      "</div>";
    document.documentElement.appendChild(panel);

    els = {
      panel: panel,
      header: panel.querySelector("#ple-header"),
      toggle: panel.querySelector("#ple-toggle"),
      page: panel.querySelector("#ple-page"),
      unique: panel.querySelector("#ple-unique"),
      dupes: panel.querySelector("#ple-dupes"),
      status: panel.querySelector("#ple-status"),
      scan: panel.querySelector("#ple-scan"),
      csv: panel.querySelector("#ple-csv"),
      xlsx: panel.querySelector("#ple-xlsx"),
      clear: panel.querySelector("#ple-clear"),
    };

    els.toggle.addEventListener("click", function () {
      panel.classList.toggle("ple-collapsed");
    });
    els.scan.addEventListener("click", function () {
      handlers.scan && handlers.scan();
    });
    els.csv.addEventListener("click", function () {
      handlers.exportCsv && handlers.exportCsv();
    });
    els.xlsx.addEventListener("click", function () {
      handlers.exportXlsx && handlers.exportXlsx();
    });
    els.clear.addEventListener("click", function () {
      handlers.clear && handlers.clear();
    });

    makeDraggable(panel, els.header);
  }

  function makeDraggable(panel, handle) {
    var dragging = false;
    var offsetX = 0;
    var offsetY = 0;
    handle.addEventListener("mousedown", function (e) {
      dragging = true;
      var rect = panel.getBoundingClientRect();
      offsetX = e.clientX - rect.left;
      offsetY = e.clientY - rect.top;
      e.preventDefault();
    });
    document.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      panel.style.left = e.clientX - offsetX + "px";
      panel.style.top = e.clientY - offsetY + "px";
      panel.style.right = "auto";
    });
    document.addEventListener("mouseup", function () {
      dragging = false;
    });
  }

  function setStats(pageCount, unique, dupes) {
    if (!els) return;
    if (pageCount !== null && pageCount !== undefined)
      els.page.textContent = String(pageCount);
    els.unique.textContent = String(unique);
    els.dupes.textContent = String(dupes);
  }

  function setStatus(text, kind) {
    if (!els) return;
    els.status.textContent = text;
    els.status.className = "ple-status" + (kind ? " ple-status-" + kind : "");
  }

  function setBusy(busy) {
    if (!els) return;
    [els.scan, els.csv, els.xlsx, els.clear].forEach(function (b) {
      b.disabled = busy;
    });
  }

  function on(name, cb) {
    handlers[name] = cb;
  }

  global.PlePanel = {
    build: build,
    setStats: setStats,
    setStatus: setStatus,
    setBusy: setBusy,
    on: on,
  };
})(window);
