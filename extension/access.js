/*
 * access.js -- per-site permission, granted at runtime.
 *
 * Nothing is hardcoded. The extension holds no host permission until the person
 * clicks "Grant access to this site" in the popup, which calls
 * chrome.permissions.request for the current tab's origin. On grant we register
 * the content scripts for that origin (chrome.scripting.registerContentScripts)
 * so the panel loads on later visits, and inject them into the open tab now.
 *
 * Loaded by the popup (window) and the service worker (self).
 */
(function (root) {
  "use strict";

  // Files injected into a granted site, in order.
  var CONTENT_JS = ["parser.js", "storage.js", "panel.js", "content.js"];
  var CONTENT_CSS = ["panel.css"];

  function originPatternForUrl(url) {
    try {
      var u = new URL(url);
      if (u.protocol !== "https:" && u.protocol !== "http:") return null;
      return u.origin + "/*";
    } catch (e) {
      return null;
    }
  }

  function regId(pattern) {
    return "ple-" + pattern.replace(/[^a-z0-9]+/gi, "-");
  }

  function hasAccess(pattern) {
    return chrome.permissions.contains({ origins: [pattern] });
  }

  function requestAccess(pattern) {
    return chrome.permissions.request({ origins: [pattern] });
  }

  function removeAccess(pattern) {
    return chrome.permissions.remove({ origins: [pattern] });
  }

  async function registerForOrigin(pattern) {
    var id = regId(pattern);
    var existing = await chrome.scripting.getRegisteredContentScripts({ ids: [id] });
    var spec = {
      id: id,
      matches: [pattern],
      js: CONTENT_JS,
      css: CONTENT_CSS,
      runAt: "document_idle",
      persistAcrossSessions: true,
    };
    if (existing && existing.length) {
      await chrome.scripting.updateContentScripts([spec]);
    } else {
      await chrome.scripting.registerContentScripts([spec]);
    }
  }

  async function unregisterForOrigin(pattern) {
    var id = regId(pattern);
    try {
      await chrome.scripting.unregisterContentScripts({ ids: [id] });
    } catch (e) {
      /* not registered -- nothing to do */
    }
  }

  // Inject the content scripts into a tab that is open right now, so the panel
  // appears without a reload. Guarded against double-injection by content.js.
  async function injectNow(tabId) {
    await chrome.scripting.insertCSS({ target: { tabId: tabId }, files: CONTENT_CSS });
    await chrome.scripting.executeScript({
      target: { tabId: tabId },
      files: CONTENT_JS,
    });
  }

  // Make the registered set match the granted set (called on install/startup).
  async function reconcileRegistrations() {
    var granted = await chrome.permissions.getAll();
    var origins = (granted && granted.origins) || [];
    var wanted = {};
    origins.forEach(function (o) {
      wanted[regId(o)] = o;
    });
    var current = await chrome.scripting.getRegisteredContentScripts();
    var currentIds = (current || []).map(function (c) {
      return c.id;
    });
    // add missing
    for (var id in wanted) {
      if (currentIds.indexOf(id) === -1) await registerForOrigin(wanted[id]);
    }
    // drop stale
    for (var i = 0; i < currentIds.length; i++) {
      if (currentIds[i].indexOf("ple-") === 0 && !wanted[currentIds[i]]) {
        try {
          await chrome.scripting.unregisterContentScripts({ ids: [currentIds[i]] });
        } catch (e) {
          /* ignore */
        }
      }
    }
  }

  root.Access = {
    CONTENT_JS: CONTENT_JS,
    CONTENT_CSS: CONTENT_CSS,
    originPatternForUrl: originPatternForUrl,
    hasAccess: hasAccess,
    requestAccess: requestAccess,
    removeAccess: removeAccess,
    registerForOrigin: registerForOrigin,
    unregisterForOrigin: unregisterForOrigin,
    injectNow: injectNow,
    reconcileRegistrations: reconcileRegistrations,
  };
})(typeof window !== "undefined" ? window : self);
