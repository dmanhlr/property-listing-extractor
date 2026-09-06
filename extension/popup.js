/*
 * popup.js -- the toolbar popup.
 *
 * Access is per-site and granted at runtime: until the person clicks "Grant
 * access to this site" (which calls chrome.permissions.request for the current
 * tab's origin), scanning is disabled. Once granted, the popup asks the
 * background worker to register the content scripts for that origin and inject
 * them into the open tab, then runs the same parser.js the panel uses.
 */
(function () {
  "use strict";

  var FIELDNAMES = [
    "listing_url", "address_full", "suburb", "state", "postcode",
    "price_text", "price_value", "property_type", "bedrooms", "bathrooms",
    "car_spaces", "land_size", "description", "agent_name", "agency_name",
    "listing_date", "image_urls",
  ];

  var state = { pattern: null, origin: null, granted: false, injectable: false };

  var $ = function (id) {
    return document.getElementById(id);
  };

  function setStatus(text) {
    $("status").textContent = text;
  }

  function setBusy(busy) {
    ["scan", "csv", "xlsx", "clear"].forEach(function (id) {
      $(id).disabled = busy;
    });
    applyGateState();
  }

  function stamp() {
    var d = new Date();
    var p = function (n) {
      return String(n).padStart(2, "0");
    };
    return (
      d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "-" +
      p(d.getHours()) + p(d.getMinutes())
    );
  }

  async function activeTab() {
    var tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    return tabs[0];
  }

  function applyGateState() {
    // Scanning needs an explicit grant for this origin.
    if (!state.granted) $("scan").disabled = true;
  }

  function renderAccess() {
    var el = $("access");
    if (!state.injectable) {
      el.className = "access blocked";
      el.textContent =
        "This page can't be scanned (not an http/https site).";
      $("scan").disabled = true;
      return;
    }
    if (state.granted) {
      el.className = "access granted";
      el.innerHTML =
        "Access granted for <b>" +
        escapeHtml(state.origin) +
        "</b>. <span class='link' id='revoke'>Remove access</span>";
      $("revoke").addEventListener("click", onRevoke);
    } else {
      el.className = "access blocked";
      el.innerHTML =
        "No access to <b>" +
        escapeHtml(state.origin) +
        "</b>. Grant it to scan this site.";
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Grant access to this site";
      btn.addEventListener("click", onGrant);
      el.appendChild(btn);
    }
    applyGateState();
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  async function refreshAccess() {
    var tab = await activeTab();
    state.tabId = tab && tab.id;
    state.pattern = tab ? window.Access.originPatternForUrl(tab.url || "") : null;
    state.injectable = !!state.pattern;
    state.origin = state.pattern ? state.pattern.replace(/\/\*$/, "") : "(this page)";
    state.granted = state.pattern
      ? await window.Access.hasAccess(state.pattern)
      : false;
    renderAccess();
    if (!state.granted && state.injectable) {
      setStatus("Grant access to this site to scan.");
    }
  }

  async function onGrant() {
    try {
      var ok = await window.Access.requestAccess(state.pattern);
      if (!ok) {
        setStatus("Access was not granted.");
        return;
      }
      await chrome.runtime.sendMessage({
        type: "PLE_ACCESS_GRANTED",
        pattern: state.pattern,
        tabId: state.tabId,
      });
      await refreshAccess();
      setStatus("Access granted. Click “Scan this tab”.");
    } catch (e) {
      setStatus("Grant failed: " + e.message);
    }
  }

  async function onRevoke() {
    try {
      await window.Access.removeAccess(state.pattern);
      await refreshAccess();
      setStatus("Access removed for this site.");
    } catch (e) {
      setStatus("Could not remove access: " + e.message);
    }
  }

  async function refreshStats(pageCount) {
    var st = await window.Collector.load();
    var c = window.Collector.counts(st);
    if (pageCount !== null && pageCount !== undefined)
      $("page").textContent = String(pageCount);
    $("unique").textContent = String(c.unique);
    $("dupes").textContent = String(c.duplicatesSkipped);
    var hasRows = c.unique > 0;
    $("csv").disabled = !hasRows;
    $("xlsx").disabled = !hasRows;
    if (st.lastStatus && state.granted) $("status").textContent = st.lastStatus;
  }

  function csvCell(name, value) {
    if (name === "image_urls" && Array.isArray(value)) value = value.join(";");
    if (value === null || value === undefined) value = "";
    value = String(value);
    if (/[",\r\n]/.test(value)) value = '"' + value.replace(/"/g, '""') + '"';
    return value;
  }

  function toCsv(rows) {
    var lines = [FIELDNAMES.join(",")];
    rows.forEach(function (row) {
      lines.push(
        FIELDNAMES.map(function (n) {
          return csvCell(n, row[n]);
        }).join(",")
      );
    });
    return lines.join("\r\n") + "\r\n";
  }

  function sendToBackground(message) {
    return new Promise(function (resolve, reject) {
      chrome.runtime.sendMessage(message, function (response) {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        if (!response || !response.ok) {
          reject(new Error((response && response.error) || "export failed"));
          return;
        }
        resolve(response);
      });
    });
  }

  async function onScan() {
    if (!state.granted) {
      setStatus("Grant access to this site first.");
      return;
    }
    setBusy(true);
    try {
      var tab = await activeTab();
      if (!tab || !tab.id) {
        setStatus("No active tab.");
        return;
      }
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["parser.js"],
      });
      var results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: function () {
          return window.ListingParser.extractListingsFromDom();
        },
      });
      var payload = results && results[0] && results[0].result;
      if (!payload || !payload.hadScript) {
        setStatus("No embedded listing data found on this tab.");
        await refreshStats(0);
        return;
      }
      var merge = await window.Collector.addRows(payload.listings);
      await refreshStats(payload.listings.length);
      var msg =
        "Scanned " + merge.seen + ": " + merge.added + " new, " +
        merge.dupes + " duplicate" + (merge.dupes === 1 ? "" : "s") + ".";
      if (merge.noUrl) msg += " " + merge.noUrl + " had no link.";
      setStatus(msg);
      await window.Collector.setStatus(msg);
    } catch (e) {
      setStatus("Scan failed: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onExportCsv() {
    setBusy(true);
    try {
      var rows = window.Collector.rowsOf(await window.Collector.load());
      if (!rows.length) {
        setStatus("Nothing collected yet.");
        return;
      }
      await sendToBackground({
        type: "PLE_DOWNLOAD",
        url: "data:text/csv;charset=utf-8," + encodeURIComponent(toCsv(rows)),
        filename: "listings-" + stamp() + ".csv",
      });
      setStatus("Exported " + rows.length + " rows to CSV.");
    } catch (e) {
      setStatus("CSV export failed: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onExportXlsx() {
    setBusy(true);
    try {
      var rows = window.Collector.rowsOf(await window.Collector.load());
      if (!rows.length) {
        setStatus("Nothing collected yet.");
        return;
      }
      await sendToBackground({
        type: "PLE_EXPORT_XLSX",
        rows: rows,
        fieldnames: FIELDNAMES,
        filename: "listings-" + stamp() + ".xlsx",
      });
      setStatus("Exported " + rows.length + " rows to XLSX.");
    } catch (e) {
      setStatus("XLSX export failed: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onClear() {
    setBusy(true);
    try {
      await window.Collector.clear();
      await refreshStats(0);
      setStatus("Cleared.");
    } finally {
      setBusy(false);
    }
  }

  $("scan").addEventListener("click", onScan);
  $("csv").addEventListener("click", onExportCsv);
  $("xlsx").addEventListener("click", onExportXlsx);
  $("clear").addEventListener("click", onClear);

  (async function init() {
    await refreshAccess();
    await refreshStats(null);
  })();
})();
