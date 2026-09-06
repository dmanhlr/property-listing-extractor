/*
 * background.js -- the service worker.
 *
 * Two jobs:
 *   1. Own the runtime content-script registration: keep the registered set in
 *      step with the host permissions the person has granted (access.js).
 *   2. Build the XLSX workbook with bundled SheetJS (vendor/xlsx.full.min.js --
 *      MV3's CSP forbids a CDN script) and issue downloads, the only context
 *      that can call chrome.downloads.
 */
importScripts("access.js", "vendor/xlsx.full.min.js");

// --- runtime access: keep registrations in step with granted permissions ----

chrome.runtime.onInstalled.addListener(function () {
  Access.reconcileRegistrations();
});
chrome.runtime.onStartup.addListener(function () {
  Access.reconcileRegistrations();
});
chrome.permissions.onRemoved.addListener(function (perms) {
  (perms.origins || []).forEach(function (origin) {
    Access.unregisterForOrigin(origin);
  });
});

// --- messages -------------------------------------------------------------

function cell(name, value) {
  if (name === "image_urls" && Array.isArray(value)) return value.join(";");
  if (value === null || value === undefined) return "";
  return value;
}

function buildXlsxDataUrl(rows, fieldnames) {
  if (typeof XLSX === "undefined") throw new Error("SheetJS not loaded");
  var aoa = [fieldnames];
  rows.forEach(function (row) {
    aoa.push(
      fieldnames.map(function (name) {
        return cell(name, row[name]);
      })
    );
  });
  var ws = XLSX.utils.aoa_to_sheet(aoa);
  ws["!freeze"] = { xSplit: 0, ySplit: 1 };
  ws["!autofilter"] = {
    ref: XLSX.utils.encode_range({
      s: { r: 0, c: 0 },
      e: { r: aoa.length - 1, c: fieldnames.length - 1 },
    }),
  };
  var wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "listings");
  var b64 = XLSX.write(wb, { type: "base64", bookType: "xlsx" });
  return (
    "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," +
    b64
  );
}

function download(url, filename) {
  return new Promise(function (resolve, reject) {
    chrome.downloads.download({ url: url, filename: filename }, function (id) {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(id);
    });
  });
}

chrome.runtime.onMessage.addListener(function (message, _sender, sendResponse) {
  (async function () {
    try {
      if (message.type === "PLE_ACCESS_GRANTED") {
        // The popup already called chrome.permissions.request. Register the
        // content scripts for the origin and inject into the open tab now.
        await Access.registerForOrigin(message.pattern);
        if (message.tabId) await Access.injectNow(message.tabId);
        sendResponse({ ok: true });
      } else if (message.type === "PLE_DOWNLOAD") {
        await download(message.url, message.filename);
        sendResponse({ ok: true });
      } else if (message.type === "PLE_EXPORT_XLSX") {
        var url = buildXlsxDataUrl(message.rows, message.fieldnames);
        await download(url, message.filename);
        sendResponse({ ok: true });
      } else {
        sendResponse({ ok: false, error: "unknown message type" });
      }
    } catch (e) {
      sendResponse({ ok: false, error: e.message });
    }
  })();
  return true; // keep the message channel open for the async response
});
