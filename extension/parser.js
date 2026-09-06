/*
 * parser.js -- the single listing parser, shared by:
 *   - the content script (reads the <script> tag text on the page),
 *   - the popup (via chrome.scripting.executeScript),
 *   - the parity test (`node extension/parser.js <file.html>` prints JSON rows).
 *
 * It is a straight port of the Python package (blob.py + shape.py + mapping.py).
 * The parity test asserts the two produce identical row sets for every fixture.
 *
 * No imports/exports: it must run as a plain script in a browser and under Node.
 */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
    if (require.main === module) {
      runCli(api);
    }
  }
  if (typeof window !== "undefined") window.ListingParser = api;
  else if (typeof self !== "undefined") self.ListingParser = api;
  else if (typeof globalThis !== "undefined") globalThis.ListingParser = api;

  function runCli(api) {
    var fs = require("fs");
    var file = process.argv[2];
    if (!file) {
      process.stderr.write("usage: node parser.js <file.html>\n");
      process.exit(2);
    }
    var html = fs.readFileSync(file, "utf8");
    var rows = api.parseListingsFromHtml(html);
    process.stdout.write(JSON.stringify(rows, null, 2) + "\n");
  }
})(this, function () {
  "use strict";

  // Output columns, in order. Matches listing_extractor.schema.FIELDNAMES.
  var FIELDNAMES = [
    "listing_url",
    "address_full",
    "suburb",
    "state",
    "postcode",
    "price_text",
    "price_value",
    "property_type",
    "bedrooms",
    "bathrooms",
    "car_spaces",
    "land_size",
    "description",
    "agent_name",
    "agency_name",
    "listing_date",
    "image_urls",
  ];

  var IMAGE_SIZE = "1144x858-format=webp";
  var TEMPLATE_TOKEN = /\{[^}]+\}/g;
  var PRICE_TOKEN = /\$\s?(\d{1,3}(?:[,\s]?\d{3})*(?:\.\d+)?)\s*([mMkK])?/g;
  var RANGE_HINT = /\bto\b|\bfrom\b|[-–—]/i;
  var ASSIGN_RE = /window\.ArgonautExchange\s*=\s*/;
  var SCRIPT_RE = /<script\b[^>]*>([\s\S]*?)<\/script>/gi;
  var MAX_DEPTH = 60;

  var ID_KEYS = ["listingId", "id"];
  var SHAPE_KEYS = ["propertyType", "generalFeatures", "productDepth", "price"];
  var PROJECT_HINTS = [
    "project",
    "new apartments",
    "new apartment",
    "new land",
    "development",
  ];

  // ---- blob: find the assignment, scan one balanced object, un-stringify ----

  function scanBalanced(s, i) {
    var n = s.length;
    while (i < n && " \t\r\n".indexOf(s[i]) !== -1) i++;
    if (i >= n || (s[i] !== "{" && s[i] !== "[")) {
      throw new Error("no JSON object at the assignment");
    }
    var start = i;
    var depth = 0;
    var inStr = false;
    var esc = false;
    while (i < n) {
      var c = s[i];
      if (inStr) {
        if (esc) esc = false;
        else if (c === "\\") esc = true;
        else if (c === '"') inStr = false;
      } else if (c === '"') {
        inStr = true;
      } else if (c === "{" || c === "[") {
        depth++;
      } else if (c === "}" || c === "]") {
        depth--;
        if (depth === 0) {
          return [JSON.parse(s.slice(start, i + 1)), i + 1];
        }
      }
      i++;
    }
    throw new Error("unterminated JSON object");
  }

  function iterScriptTexts(html) {
    var out = [];
    var m;
    SCRIPT_RE.lastIndex = 0;
    while ((m = SCRIPT_RE.exec(html)) !== null) out.push(m[1]);
    if (out.length === 0) out.push(html);
    return out;
  }

  function extractBlob(html) {
    var texts = iterScriptTexts(html);
    for (var t = 0; t < texts.length; t++) {
      var text = texts[t];
      var m = ASSIGN_RE.exec(text);
      if (!m) continue;
      try {
        return scanBalanced(text, m.index + m[0].length)[0];
      } catch (e) {
        continue;
      }
    }
    return {};
  }

  function maybeJson(value) {
    if (typeof value === "string") {
      var t = value.replace(/^\s+/, "");
      if (t[0] === "{" || t[0] === "[") {
        try {
          return JSON.parse(value);
        } catch (e) {
          return value;
        }
      }
    }
    return value;
  }

  function isPlainObject(v) {
    return v !== null && typeof v === "object" && !Array.isArray(v);
  }

  // ---- shape ----

  function get(d, path) {
    var cur = d;
    for (var i = 0; i < path.length; i++) {
      if (!isPlainObject(cur)) return null;
      cur = cur[path[i]];
      if (cur === undefined || cur === null) return null;
    }
    return cur;
  }

  function looksLikeListing(d) {
    if (!isPlainObject(d)) return false;
    var addr = d.address;
    if (!isPlainObject(addr)) return false;
    if (!addr.suburb) return false;
    var hasId =
      ID_KEYS.some(function (k) {
        return k in d;
      }) || isPlainObject(d._links);
    var hasShape = SHAPE_KEYS.some(function (k) {
      return k in d;
    });
    return hasId && hasShape;
  }

  function listingKey(d) {
    return String(d.listingId || d.id || "anon");
  }

  function listingKind(d) {
    var parts = [
      get(d, ["propertyType", "display"]),
      get(d, ["propertyType", "id"]),
      d.channel,
      d.productType,
    ]
      .filter(Boolean)
      .map(function (x) {
        return String(x).toLowerCase();
      });
    var hay = parts.join(" ");
    for (var i = 0; i < PROJECT_HINTS.length; i++) {
      if (hay.indexOf(PROJECT_HINTS[i]) !== -1) return "project";
    }
    return "standard";
  }

  function iterListings(node, seen, out) {
    node = maybeJson(node);
    if (isPlainObject(node)) {
      if (looksLikeListing(node)) {
        var key = listingKey(node);
        if (!seen.has(key)) {
          seen.add(key);
          out.push(node);
        }
      }
      var vals = Object.values(node);
      for (var i = 0; i < vals.length; i++) iterListings(vals[i], seen, out);
    } else if (Array.isArray(node)) {
      for (var j = 0; j < node.length; j++) iterListings(node[j], seen, out);
    }
    return out;
  }

  function findMaxPage(node, depth) {
    depth = depth || 0;
    if (depth > MAX_DEPTH) return null;
    node = maybeJson(node);
    if (isPlainObject(node)) {
      var keys = ["maxPageNumberAvailable", "maxPageNumber", "totalPages"];
      for (var k = 0; k < keys.length; k++) {
        var v = node[keys[k]];
        if (typeof v === "number" && Number.isInteger(v) && v > 0) return v;
      }
      var vals = Object.values(node);
      for (var i = 0; i < vals.length; i++) {
        var r = findMaxPage(vals[i], depth + 1);
        if (r) return r;
      }
    } else if (Array.isArray(node)) {
      for (var j = 0; j < node.length; j++) {
        var r2 = findMaxPage(node[j], depth + 1);
        if (r2) return r2;
      }
    }
    return null;
  }

  // ---- mapping ----

  function feature(raw, name) {
    var v = get(raw, ["generalFeatures", name, "value"]);
    if (v === null) v = get(raw, ["generalFeatures", name]);
    if (v === null) v = raw[name];
    if (isPlainObject(v)) v = v.value;
    if (typeof v === "boolean") return "";
    return typeof v === "number" ? v : v || "";
  }

  function parsePriceValue(text) {
    if (!text) return null;
    if (RANGE_HINT.test(text)) return null;
    PRICE_TOKEN.lastIndex = 0;
    var matches = [];
    var m;
    while ((m = PRICE_TOKEN.exec(text)) !== null) matches.push(m);
    if (matches.length !== 1) return null;
    var num = matches[0][1];
    var suffix = matches[0][2] || "";
    var val = parseFloat(num.replace(/[, ]/g, ""));
    if (Number.isNaN(val)) return null;
    if (suffix.toLowerCase() === "m") val *= 1000000;
    else if (suffix.toLowerCase() === "k") val *= 1000;
    return val > 0 ? val : null;
  }

  function expandImageUrl(url) {
    return url.replace(TEMPLATE_TOKEN, IMAGE_SIZE);
  }

  function images(raw) {
    var imgs = get(raw, ["media", "images"]) || raw.images || [];
    var out = [];
    for (var i = 0; i < imgs.length; i++) {
      var im = imgs[i];
      var url = "";
      if (typeof im === "string") url = im;
      else if (isPlainObject(im))
        url = im.templatedUrl || im.url || im.href || "";
      if (url) out.push(expandImageUrl(url));
    }
    return out;
  }

  function agents(raw) {
    var listers = raw.listers || get(raw, ["advertising", "listers"]) || [];
    var names = [];
    for (var i = 0; i < listers.length; i++) {
      if (isPlainObject(listers[i])) {
        var name = (listers[i].name || "").trim();
        if (name) names.push(name);
      }
    }
    return names.join("; ");
  }

  function landSize(raw) {
    var land = get(raw, ["propertySizes", "land"]) || {};
    var disp = land.displayValue || land.value || "";
    var unit =
      get(land, ["sizeUnit", "displayValue"]) || get(land, ["sizeUnit", "id"]) || "";
    if (disp && unit) return (disp + " " + unit).trim();
    return String(disp || raw.landSize || "");
  }

  function canonicalUrl(raw, baseUrl) {
    var href =
      get(raw, ["_links", "canonical", "href"]) || get(raw, ["_links", "canonical"]);
    if (typeof href === "string" && href && href.indexOf("{") === -1) {
      if (href.indexOf("http") === 0) return href;
      // Absolutise against the origin the page was loaded from; with no origin
      // context (Node parity run) keep the path relative.
      return baseUrl ? baseUrl.replace(/\/+$/, "") + href : href;
    }
    return "";
  }

  function priceText(raw) {
    return (
      get(raw, ["price", "display"]) ||
      get(raw, ["priceDetails", "displayPrice"]) ||
      get(raw, ["priceDetails", "price"]) ||
      raw.displayPrice ||
      ""
    );
  }

  function mapListing(raw, baseUrl) {
    var pText = priceText(raw);
    var pVal = get(raw, ["price", "value"]);
    if (typeof pVal === "boolean" || typeof pVal !== "number") pVal = null;
    if (pVal !== null && pVal <= 0) pVal = null;
    if (pVal === null) pVal = parsePriceValue(pText);

    var ptype =
      get(raw, ["propertyType", "display"]) ||
      get(raw, ["propertyType", "id"]) ||
      "";

    return {
      listing_url: canonicalUrl(raw, baseUrl),
      address_full:
        get(raw, ["address", "display", "fullAddress"]) ||
        get(raw, ["address", "display", "shortAddress"]) ||
        get(raw, ["address", "fullAddress"]) ||
        "",
      suburb: get(raw, ["address", "suburb"]) || "",
      state: (get(raw, ["address", "state"]) || "").toUpperCase(),
      postcode: String(get(raw, ["address", "postcode"]) || ""),
      price_text: pText,
      price_value: pVal,
      property_type: ptype,
      bedrooms: feature(raw, "bedrooms"),
      bathrooms: feature(raw, "bathrooms"),
      car_spaces: feature(raw, "parkingSpaces"),
      land_size: landSize(raw),
      description: (raw.description || "").trim(),
      agent_name: agents(raw),
      agency_name:
        get(raw, ["listingCompany", "name"]) ||
        get(raw, ["advertising", "agency", "name"]) ||
        "",
      listing_date:
        raw.dateListed ||
        get(raw, ["dateListed", "value"]) ||
        raw.listingDateDisplay ||
        "",
      image_urls: images(raw),
      listing_kind: listingKind(raw),
    };
  }

  // ---- public ----

  function rawListingsFromHtml(html) {
    return iterListings(extractBlob(html), new Set(), []);
  }

  function parseListingsFromText(text, baseUrl) {
    var blob = extractBlob(text);
    return iterListings(blob, new Set(), []).map(function (raw) {
      return mapListing(raw, baseUrl);
    });
  }

  function parseListingsFromHtml(html, baseUrl) {
    return parseListingsFromText(html, baseUrl);
  }

  // Browser-only: read the script tag on the current page (never the wiped
  // window.ArgonautExchange variable).
  function extractListingsFromDom() {
    if (typeof document === "undefined") {
      return { hadScript: false, hadBlob: false, listings: [], maxPage: null };
    }
    var script = Array.prototype.find.call(document.scripts, function (s) {
      return s.textContent && s.textContent.indexOf("ArgonautExchange") !== -1;
    });
    if (!script) {
      return { hadScript: false, hadBlob: false, listings: [], maxPage: null };
    }
    var blob = extractBlob(script.textContent);
    var hadBlob = blob && Object.keys(blob).length > 0;
    var baseUrl = typeof location !== "undefined" ? location.origin : undefined;
    var rows = iterListings(blob, new Set(), []).map(function (raw) {
      return mapListing(raw, baseUrl);
    });
    return {
      hadScript: true,
      hadBlob: !!hadBlob,
      listings: rows,
      maxPage: findMaxPage(blob),
      url: typeof location !== "undefined" ? location.href : "",
    };
  }

  return {
    FIELDNAMES: FIELDNAMES,
    parseListingsFromHtml: parseListingsFromHtml,
    parseListingsFromText: parseListingsFromText,
    rawListingsFromHtml: rawListingsFromHtml,
    extractListingsFromDom: extractListingsFromDom,
    extractBlob: extractBlob,
    mapListing: mapListing,
    looksLikeListing: looksLikeListing,
    parsePriceValue: parsePriceValue,
    expandImageUrl: expandImageUrl,
    findMaxPage: findMaxPage,
  };
});
