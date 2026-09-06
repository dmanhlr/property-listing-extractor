/*
 * popup.js -- the toolbar popup. It runs the same parser.js in the active tab
 * via chrome.scripting.executeScript, then merges the rows into the same store
 * the in-page panel uses. Exports go through the background worker.
 */
(function () {
  "use strict";

  var FIELDNAMES = [
    "listing_url", "address_full", "suburb", "state", "postcode",
    "price_text", "price_value", "property_type", "bedrooms", "bathrooms",
    "car_spaces", "land_size", "description", "agent_name", "agency_name",
    "listing_date", "image_urls",
  ];

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

  async function refreshStats(pageCount) {
    var state = await window.Collector.load();
    var c = window.Collector.counts(state);
    if (pageCount !== null && pageCount !== undefined)
      $("page").textContent = String(pageCount);
    $("unique").textContent = String(c.unique);
    $("dupes").textContent = String(c.duplicatesSkipped);
    if (state.lastStatus) $("status").textContent = state.lastStatus;
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

  document.getElementById("scan").addEventListener("click", onScan);
  document.getElementById("csv").addEventListener("click", onExportCsv);
  document.getElementById("xlsx").addEventListener("click", onExportXlsx);
  document.getElementById("clear").addEventListener("click", onClear);
  refreshStats(null);
})();
