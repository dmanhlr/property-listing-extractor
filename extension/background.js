/*
 * background.js -- the service worker. It is the only context that calls
 * chrome.downloads. It also builds the XLSX workbook with SheetJS, which is
 * bundled offline (vendor/xlsx.full.min.js) because Manifest V3's CSP forbids
 * loading a script from a CDN at runtime.
 */
importScripts("vendor/xlsx.full.min.js");

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
      if (message.type === "PLE_DOWNLOAD") {
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
