/*
 * content.js -- glue between the in-page panel, the shared parser and the
 * store. No auto-navigation and no background crawling: a scan happens only
 * when the person clicks "Scan this page".
 */
(function () {
  "use strict";

  var FIELDNAMES = window.ListingParser.FIELDNAMES;

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
        FIELDNAMES.map(function (name) {
          return csvCell(name, row[name]);
        }).join(",")
      );
    });
    return lines.join("\r\n") + "\r\n";
  }

  function stamp() {
    var d = new Date();
    var p = function (n) {
      return String(n).padStart(2, "0");
    };
    return (
      d.getFullYear() +
      p(d.getMonth() + 1) +
      p(d.getDate()) +
      "-" +
      p(d.getHours()) +
      p(d.getMinutes())
    );
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

  async function refreshStats(pageCount) {
    var state = await window.Collector.load();
    var c = window.Collector.counts(state);
    window.PlePanel.setStats(pageCount, c.unique, c.duplicatesSkipped);
  }

  async function onScan() {
    window.PlePanel.setBusy(true);
    try {
      var result = window.ListingParser.extractListingsFromDom();
      if (!result.hadScript) {
        window.PlePanel.setStatus(
          "No embedded listing data found on this page.",
          "error"
        );
        await refreshStats(0);
        return;
      }
      var merge = await window.Collector.addRows(result.listings);
      window.PlePanel.setStats(result.listings.length, null, null);
      await refreshStats(result.listings.length);
      var msg =
        "Scanned " +
        merge.seen +
        " listing" +
        (merge.seen === 1 ? "" : "s") +
        ": " +
        merge.added +
        " new, " +
        merge.dupes +
        " duplicate" +
        (merge.dupes === 1 ? "" : "s") +
        ".";
      if (merge.noUrl) msg += " " + merge.noUrl + " had no link (skipped).";
      window.PlePanel.setStatus(msg, "ok");
      await window.Collector.setStatus(msg);
    } catch (e) {
      window.PlePanel.setStatus("Scan failed: " + e.message, "error");
    } finally {
      window.PlePanel.setBusy(false);
    }
  }

  async function exportCsv() {
    window.PlePanel.setBusy(true);
    try {
      var state = await window.Collector.load();
      var rows = window.Collector.rowsOf(state);
      if (!rows.length) {
        window.PlePanel.setStatus("Nothing collected yet.", "error");
        return;
      }
      var dataUrl =
        "data:text/csv;charset=utf-8," + encodeURIComponent(toCsv(rows));
      await sendToBackground({
        type: "PLE_DOWNLOAD",
        url: dataUrl,
        filename: "listings-" + stamp() + ".csv",
      });
      window.PlePanel.setStatus("Exported " + rows.length + " rows to CSV.", "ok");
    } catch (e) {
      window.PlePanel.setStatus("CSV export failed: " + e.message, "error");
    } finally {
      window.PlePanel.setBusy(false);
    }
  }

  async function exportXlsx() {
    window.PlePanel.setBusy(true);
    try {
      var state = await window.Collector.load();
      var rows = window.Collector.rowsOf(state);
      if (!rows.length) {
        window.PlePanel.setStatus("Nothing collected yet.", "error");
        return;
      }
      await sendToBackground({
        type: "PLE_EXPORT_XLSX",
        rows: rows,
        fieldnames: FIELDNAMES,
        filename: "listings-" + stamp() + ".xlsx",
      });
      window.PlePanel.setStatus(
        "Exported " + rows.length + " rows to XLSX.",
        "ok"
      );
    } catch (e) {
      window.PlePanel.setStatus("XLSX export failed: " + e.message, "error");
    } finally {
      window.PlePanel.setBusy(false);
    }
  }

  async function clearAll() {
    window.PlePanel.setBusy(true);
    try {
      await window.Collector.clear();
      await refreshStats(0);
      window.PlePanel.setStatus("Cleared.", "ok");
    } finally {
      window.PlePanel.setBusy(false);
    }
  }

  window.PlePanel.build();
  window.PlePanel.on("scan", onScan);
  window.PlePanel.on("exportCsv", exportCsv);
  window.PlePanel.on("exportXlsx", exportXlsx);
  window.PlePanel.on("clear", clearAll);
  refreshStats(null);
})();
