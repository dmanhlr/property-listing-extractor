/*
 * storage.js -- the collected-listings store, kept in chrome.storage.local.
 * Used by the content script and the popup. Not loaded by Node.
 *
 * Shape:
 *   {
 *     listings: { <listing_url>: row, ... },   // deduped by listing_url
 *     duplicatesSkipped: <int>,                 // cumulative
 *     lastStatus: <string>,
 *     lastScanCount: <int>                      // listings seen on the last scan
 *   }
 */
(function (root) {
  "use strict";

  var KEY = "collector_v1";

  function empty() {
    return { listings: {}, duplicatesSkipped: 0, lastStatus: "", lastScanCount: 0 };
  }

  async function load() {
    try {
      var got = await chrome.storage.local.get(KEY);
      return Object.assign(empty(), got[KEY] || {});
    } catch (e) {
      return empty();
    }
  }

  async function save(state) {
    var payload = {};
    payload[KEY] = state;
    await chrome.storage.local.set(payload);
    return state;
  }

  // Merge freshly scanned rows. A row with no listing_url cannot be deduped and
  // is not stored (validation would drop it anyway); it still counts as seen.
  async function addRows(rows) {
    var state = await load();
    var added = 0;
    var dupes = 0;
    var noUrl = 0;
    rows.forEach(function (row) {
      if (!row.listing_url) {
        noUrl++;
        return;
      }
      if (state.listings[row.listing_url]) dupes++;
      else added++;
      state.listings[row.listing_url] = row;
    });
    state.duplicatesSkipped += dupes;
    state.lastScanCount = rows.length;
    await save(state);
    return { seen: rows.length, added: added, dupes: dupes, noUrl: noUrl };
  }

  async function setStatus(text) {
    var state = await load();
    state.lastStatus = text;
    await save(state);
  }

  async function clear() {
    await save(empty());
  }

  function rowsOf(state) {
    return Object.keys(state.listings).map(function (k) {
      return state.listings[k];
    });
  }

  function counts(state) {
    return {
      unique: Object.keys(state.listings).length,
      duplicatesSkipped: state.duplicatesSkipped,
      lastScanCount: state.lastScanCount,
    };
  }

  root.Collector = {
    KEY: KEY,
    empty: empty,
    load: load,
    save: save,
    addRows: addRows,
    setStatus: setStatus,
    clear: clear,
    rowsOf: rowsOf,
    counts: counts,
  };
})(typeof window !== "undefined" ? window : self);
