# SimpleInventory-WebUI
Thanks for the Really good and easy to use Inventory in Homeassistant. This is really something i was searching for, for a long time. 
All credits go to: https://github.com/blaineventurine/simple_inventory

Current development: **0.4.0-dev**, localization, display preferences and a shared visual design. Previous functional baseline: **0.3.0**. Saved baseline: **0.1.0**. See [changelog](CHANGELOG.md) and [version recovery notes](docs/versioning.md).

A Python web interface for the Simple Inventory integration in Home Assistant.

Made with AI, since i can do some coding, but by far not enough to pull this off.

## Current state

This repository now contains the functional WebUI, installation scripts and credential policy. Existing LICENSE is retained. Private HA settings are configured manually after installation.

## Architecture

Browser -> Python FastAPI application -> authenticated Home Assistant WebSocket API -> Simple Inventory.
Home Assistant remains the source of truth; no separate inventory database is required. The application depends on HA being available.

- FastAPI: routes, input validation and application logic.
- Uvicorn: HTTP server.
- Jinja2 plus local HTML/CSS and minimal JavaScript: responsive user interface; no Node.js build service required.
- websockets: Home Assistant connection, authentication, request IDs, reconnection and event subscriptions.
- httpx: HTTP calls if needed.
- pydantic-settings: configuration from manually supplied runtime settings.
- python-multipart: HTML form handling.
- itsdangerous: signed sessions and expiring forms with CSRF protection.
- systemd (provided by the Debian container): service startup and restart.

The v0.3.0 feature scope includes selecting existing inventories, displaying items, creating and editing items, editable suggestions for units/groups/locations, and euro values. Inventory administration stays in Home Assistant. Uncertain write results are reported without automatic retries.

## One-command Proxmox installation

Run as root in the **Proxmox host shell**:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/VexMex/SimpleInventory-WebUI/main/install.sh)"
```

The host needs curl, normally available on Proxmox. Review install.sh before running it. A download failure must not be mistaken for success: a setup banner and prompts must appear. The short launcher follows the Community Scripts invocation style.

The installer asks for container ID, hostname, disk storage, template storage, bridge, CPU, memory and disk size, then asks for confirmation. Enter accepts the suggested value. Defaults: a free ID, Debian 13 amd64, unprivileged, 1 core, 1 GB RAM, 4 GB disk, DHCP. Nesting is enabled for systemd 257 compatibility. No GPU or Docker is required. Automatic startup on host boot is disabled for this development foundation.

It downloads the Debian template when needed, creates a NEW LXC, starts it, installs dependencies and enables the WebUI on HTTP port 80. Existing guests are never reused or deleted. On failure a new guest is retained for diagnosis. Cancelling creates no guest.

The guest bootstrap is pinned to a reviewed revision and SHA-256 checksum. The entry script on main can change; Python dependencies still use development ranges. A production release requires full dependency locking.

For automated tests, SIW_NONINTERACTIVE=1 skips prompts. SIW_CTID, SIW_HOSTNAME, SIW_STORAGE, SIW_TEMPLATE_STORAGE, SIW_BRIDGE, SIW_CORES, SIW_MEMORY and SIW_DISK override defaults. Existing IDs are rejected. Credentials are never installer arguments.

**Current result:** a WebUI on HTTP port 80 plus manual HA setup. No HA token is requested by the installer. After creation, run `/usr/local/bin/simpleinventory-setup` inside the LXC; see [HA setup](docs/ha-setup.md). The host installer is self-contained; it follows the host/guest split without sourcing changing Community Scripts helper libraries.

See [guest bootstrap test](docs/bootstrap-test.md).

## Credentials

Read SECURITY.md and AGENTS.md before changing or uploading anything. Real credentials never belong on GitHub. The user permits local runtime storage in the installation LXC: /etc/simpleinventory-webui/app.env, outside the source tree, owned by root with mode 0600. Manual HA token configuration, a boot-time connection check and the WebUI are implemented. Optional shared-password authentication is prepared but disabled by default.

References:
- https://github.com/blaineventurine/simple_inventory
- https://github.com/community-scripts/ProxmoxVE/blob/main/ct/homebox.sh
- https://github.com/community-scripts/ProxmoxVE/blob/main/install/homebox-install.sh
- https://fastapi.tiangolo.com/

## Opening the LXC console

The installer sets the Proxmox console mode to shell. Opening Console in the Proxmox web interface starts a root shell directly, without a guest username/password prompt. Access is controlled by Proxmox authentication and console permissions. This does not set an empty root password or enable passwordless SSH. The container remains unprivileged.

Run /usr/local/bin/simpleinventory-setup from that console to configure HA manually.

## First WebUI

Open the LXC IPv4 address or a DNS name pointing to it in a browser using HTTP. Port 80 needs no explicit suffix. The page discovers existing inventories and selects the alphabetically first inventory by default. Choose an inventory in the dropdown and click **Anzeigen**. The page displays the selected inventory and item name, quantity, unit, category and location. Refresh the page to reload HA values. Use **Artikel hinzufügen** to create an item and **Bearbeiten** beside a row to edit it. Supported fields are name, quantity, unit, value per unit (EUR), category and location. New items default to the unit `stück`. Unit fields offer existing units as editable dropdown suggestions. Values are entered as numbers and displayed with the euro symbol. Group and location fields offer existing values from the selected inventory as dropdown suggestions. You can also type new values; they are created when the item is saved and then appear as suggestions. Multiple categories or locations can be separated by commas. Saving writes to the selected HA inventory and reloads the overview.

See [WebUI configuration and access policy](docs/webui.md). Existing private HA settings are preserved on deployment. Running the HA setup helper again restarts the web service so it reloads the saved settings.

## Multiple inventories

Existing Simple Inventory inventories are discovered using the HA sensor states already used by the application. The dropdown is sorted by name. Selection is kept in the URL, so separate tabs can work with separate inventories. Item forms are signed for the inventory they were opened in and never follow a later selection in another tab. Unknown or removed inventory IDs produce an error instead of falling back to another inventory.

The connection helper now asks only for HA connection settings. It verifies read access to the alphabetically first available inventory, without prompting for an inventory or persisting a selection. Existing configuration files remain valid; their legacy SIW_INVENTORY_ID value is ignored. Inventory creation, renaming and deletion remain in Home Assistant and are not implemented in this WebUI.

## Language and appearance

The interface now supports German and English, defaults to the Home Assistant system language, and formats quantities, currencies and timestamps for the selected language. Open **Settings / Einstellungen** to change this browser's language, currency, light/dark mode, accent and spacing. Currency selection changes display formatting only; it never converts stored values.

Installation-wide defaults and password behavior are configured in the protected local INI file `/etc/simpleinventory-webui/settings.ini`. Browser display overrides use a cookie. Authentication settings and credentials are never controlled by that cookie. Existing HA credentials and optional web.env settings are preserved. See [configuration, supported values and persistence](docs/settings.md).
