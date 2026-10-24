# Inventory WebUI

## Access and data

The systemd service simpleinventory-web.service listens on 0.0.0.0:80. Use the LXC IPv4 address or a DNS name resolving to it in a browser. A separate DNS record must be provided by your router or DNS server if desired.

GET / displays the selected inventory and its items. GET /api/inventory provides the same selected fields as JSON. Both read fresh data from HA. GET /items/new opens a creation form. GET /items/edit?item=NAME opens an existing item. POST /items/new and POST /items/edit save through HA simple_inventory.add_item and simple_inventory.update_item services. A request may select an existing discovered inventory through the inventory query parameter. The server validates this selection before reading or writing. GET /health checks the web process, not HA connectivity.

On HA connection, authentication or inventory failure, the UI responds with a neutral message and HTTP 503. Tokens, HA addresses and upstream exception payloads are not exposed. HTML templates escape HA-provided content.

## Service and credentials

The service uses the dedicated simpleinventory-webui account, not root. Its only retained Linux capability is CAP_NET_BIND_SERVICE for port 80. Code is root-owned under /opt/simpleinventory-webui/releases, with current pointing at the deployed version.

systemd reads the root-only /etc/simpleinventory-webui/app.env and passes the HA settings to the web process. The service account does not need direct read access to that private file. Code installation never overwrites private settings. After manually changing HA configuration, restart the web service. The updated simpleinventory-setup helper does this after a successful configuration save.

The service is enabled at installation and restarts after a container reboot. Existing Proxmox onboot settings are unchanged; automatic container startup on host boot remains a separate Proxmox setting.

## Prepared shared-password mode

Default: password authentication is disabled. This means every client that can reach the port can read and change the inventory; it is not a firewall restriction.

A single-password login form is implemented with no username. Optional settings belong in /etc/simpleinventory-webui/web.env, root-owned with mode 0600. The settings are:
- SIW_AUTH_ENABLED: true to require configured authentication.
- SIW_LOCAL_BYPASS: true to bypass the password for directly connected private IPv4 subnets; false to require it for all clients.
- SIW_PASSWORD_HASH: PBKDF2-SHA256 in the format pbkdf2_sha256, 600000, a 16-byte random salt in hexadecimal and a SHA256 digest in hexadecimal, separated by dollar characters.
- SIW_SESSION_SECRET: a locally generated random secret of at least 32 characters for signed cookies.

Actual values must be generated locally and never committed. Restart simpleinventory-web.service after configuring them. Enabling authentication without valid private settings prevents service startup instead of silently disabling protection. A dedicated password-configuration helper and HTTPS deployment are future work; use HTTPS before sending passwords across untrusted networks.

The login uses signed expiring cookies, CSRF checks, bounded input and an in-memory attempt limit. It is not a multi-user system.

## Local subnet recognition

A private-looking client IP alone does not make a client local. The application reads active interface addresses and their real prefix lengths. Only directly connected IPv4 subnets fully inside RFC1918 ranges are eligible. Networks are refreshed every 30 seconds; discovery failure grants no bypass.

Thus an address with /23 uses that actual /23, not an assumed /24. The logic works with DHCP in different private networks without hardcoding one LAN. Loopback is also allowed when local bypass is enabled. IPv6 bypass is not implemented.

The server explicitly ignores forwarded HTTP headers and does not use X-Forwarded-For for authorization. A reverse proxy would require a separate trust design before being used with local bypass.

## Validation

50 automated tests passed in the Debian 13 test LXC, covering the HA setup and WebUI, including HTML escaping, empty inventories, upstream failure handling, optional password sessions, CSRF checks, login size/attempt limits, local-subnet changes and spoofed forwarding headers.

A temporary test item was created, edited and renamed through the deployed forms with real HA, then removed. Existing inventory items and the private HA configuration remained unchanged. The service runs as its dedicated non-root user and the private HA configuration file was verified unchanged. The existing v0.1.0 snapshot remains the recovery baseline.

## Editing and save protection

Editable fields are name, quantity, unit, value per unit (EUR), category and location. Quantities allow zero and up to six decimal places, using a decimal point or comma. Empty category/location clears those values. Multiple values are comma-separated. Other HA item metadata is omitted from updates so it is preserved.

Forms use signed, expiring, cookie-bound proofs even when password authentication is disabled. Replayed submissions are blocked. Before updating, the application compares the current editable values with the values shown when the form was opened. A conflict requires reopening the form. This catches changes observed before dispatch; HA does not expose an atomic conditional update, so a concurrent change in the brief interval before saving cannot be excluded.

Duplicate item names and aliases are checked before creation/renaming. After a write, the item is read again to confirm the saved fields. A connection failure after dispatch is reported as an uncertain result and is never automatically retried: check the inventory before submitting again. Form proofs expire after 15 minutes and may require reopening after a service restart.

## Group and location suggestions

Creation and editing forms offer existing category and location values from items in the selected inventory using native editable dropdowns. Suggestions refresh whenever a form is opened. Blank values are excluded, duplicates are removed and the lists are sorted. Free text is accepted: new values are created by HA when saving the item and become suggestions on the next form load. Opening a form does not create any values. Multiple values may still be entered separated by commas. Native dropdown presentation and filtering follow the browser's behavior.

## Units and euro values

Unit fields offer existing non-empty units from items in the selected inventory, plus `stück`, as editable dropdown suggestions. New items default to `stück`; editing preserves the saved unit. A newly typed unit is saved with the item and appears on subsequent form loads.

The Wert field maps to HA's existing `price` field and represents value per unit, independent of quantity. Enter a non-negative number with at most two decimal places, using a comma or decimal point. New items default to zero. The euro sign is displayed outside the input and is not submitted. The overview shows a Wert column with two decimal places and the euro symbol. Missing values appear as a dash. Numeric input and changes to price are covered by validation, stale-edit checks and post-save verification.

## Inventory selection

GET / and GET /api/inventory discover available inventory sensors and select the alphabetically first inventory when no inventory parameter is supplied. The dropdown uses GET /?inventory=ID with an Anzeigen button and lists inventories sorted by display name, then ID to break ties. Read and item-form links retain that parameter. An explicitly unknown or removed ID returns 404; it is never replaced with the default inventory. With no inventories, the overview explains that an inventory must first be configured in HA and does not offer item creation.

Each signed item form includes its original inventory ID. Saving validates that the inventory still exists and returns to that inventory. A selection change in a different tab or an added query parameter cannot redirect an existing form's write. Category, location and unit suggestions use only the selected inventory. Inventory administration is intentionally absent: no HA integration creation, update or removal commands are used.

The connection helper stores HA_URL, HA_TOKEN and HA_ALLOW_HTTP only. Legacy SIW_INVENTORY_ID settings are accepted but ignored, so an existing installation requires no credential migration or re-entry. Both manual setup and the boot check discover inventories and verify read access to the alphabetically first available inventory. No inventory or article is created by that check.

Validation includes two simulated inventories, duplicate article names across inventories, independent tab selection, signed write targeting, removed inventories and the empty-inventory-list case. Real HA discovery, default selection and the saved-connection boot check also passed. The real connection currently exposes one inventory; no additional inventory was created for testing.

## Localization and display preferences

The current development UI supports German/English translations, HA system-language and time-zone detection, localized quantities/currency/timestamps, and browser display preferences. The shared layout supports light/dark/device mode, teal/blue accents, comfortable/compact spacing and narrow-screen inventory cards. Currency changes are formatting only.

The protected installation INI is delivered to the service using systemd LoadCredential. Access-policy defaults come from its access section unless existing web.env values override them. Browser cookies control only display choices. See [settings and persistence](settings.md) for the configuration schema, supported languages/currencies, preference order, restart behavior and remaining limitations.
