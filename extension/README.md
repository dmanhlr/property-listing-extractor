# Extension route (Manifest V3)

A person browses the portal normally; this extension reads the JSON the page
already embedded and collects it into a table you export as CSV or XLSX. No
auto-navigation, no background crawling — you drive.

![panel](../docs/extension_panel.png) ![popup](../docs/extension_popup.png)

## Load it unpacked

1. Open `chrome://extensions`.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and pick this `extension/` folder.
4. The **Property Listing Collector** icon appears in the toolbar.

## Access is per-site, granted at runtime

`manifest.json` has **no host permissions and no portal origin** — nothing to
hand-edit before a real run. It declares only `optional_host_permissions`
(`https://*/*`, `http://*/*`), which grant nothing until asked.

- Open the site you want to collect from, then open the popup.
- The popup shows the current site and whether the extension has access. If not,
  click **Grant access to this site** — Chrome prompts for permission to that
  origin (`chrome.permissions.request`).
- On grant, the extension registers its content scripts for that origin
  (`chrome.scripting.registerContentScripts`, so the panel loads on later
  visits) and injects them into the open tab now.
- **Scan** is disabled until access is granted, with a message saying so.
- **Remove access** in the popup revokes the permission and unregisters the
  scripts for that site.

Relative canonical links are absolutised against the tab's own origin at
runtime — there is no base URL to configure.

## Use it

- Browse to a search-results page on the portal; grant access (above).
- The **Listing Collector** panel appears (drag it by its header; the toolbar
  popup does the same job).
- Click **Scan this page**. The panel shows listings found on the page, the
  running unique total, and duplicates skipped.
- Page through the results yourself, clicking **Scan this page** on each.
- Click **Export CSV** or **Export XLSX** when done. Files download via the
  background worker.
- **Clear** empties the collected set (`chrome.storage.local`).

## How the pieces fit

| File | Role |
|---|---|
| `parser.js` | the single parser — finds `window.ArgonautExchange` in the script **text** (the page wipes the live variable), scans one balanced object, un-stringifies nested JSON, keeps dicts that look like a listing, maps them to the 17-field row. Same file the parity test runs under Node. |
| `access.js` | per-site permission: request / remove, and register / unregister the content scripts for a granted origin. Loaded by the popup and the service worker. |
| `storage.js` | the collected set in `chrome.storage.local`, deduped by `listing_url`. |
| `panel.js` / `panel.css` | the draggable in-page panel: stats, a status line, and four keyboard-accessible buttons. |
| `content.js` | wires the panel to the parser and the store; builds the CSV; asks the background worker to download. Guards against double-injection. |
| `popup.js` / `popup.html` | the toolbar popup — the grant/remove-access control, and runs `parser.js` in the active tab via `chrome.scripting.executeScript`, into the same store. |
| `background.js` | the service worker: keeps content-script registrations in step with granted permissions; builds the XLSX with bundled SheetJS (`vendor/xlsx.full.min.js` — MV3's CSP forbids a CDN script); the only context that calls `chrome.downloads`. |

## Why a person has to drive

Automated page loads from most IPs are blocked on the first request. A real
browser driven by a person is not — so the extension never navigates for you and
never crawls in the background. For volume beyond what hand-paging can cover, see
[`../docs/routes.md`](../docs/routes.md).
