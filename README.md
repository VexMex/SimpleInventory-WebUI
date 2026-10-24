# SimpleInventory-WebUI

Current development: **0.3.0-dev**, WebUI with item creation and editing. Saved baseline: **0.1.0**. See [changelog](CHANGELOG.md) and [version recovery notes](docs/versioning.md).

A Python web interface for the Simple Inventory integration in Home Assistant.

## Current state

This repository now contains the functional WebUI, installation scripts and credential policy. Existing LICENSE is retained. Private HA settings are configured manually after installation.

## Intended architecture

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

Planned UI extensions include additional inventory selection, search/filter, quantity buttons and deletion. Original target scope: list inventories; search/filter items by category and location; create/edit items; increment/decrement quantities; confirm deletion; display successful or failed saves. The backend must reconcile uncertain write results instead of blindly retrying.

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

Open the LXC IPv4 address or a DNS name pointing to it in a browser using HTTP. Port 80 needs no explicit suffix. The page displays the configured inventory and item name, quantity, unit, category and location. Refresh the page to reload HA values. Use **Artikel hinzufügen** to create an item and **Bearbeiten** beside a row to edit it. Supported fields are name, quantity, unit, category and location. Multiple categories or locations can be separated by commas. Saving writes to the configured HA inventory and reloads the overview.

See [WebUI configuration and access policy](docs/webui.md). Existing private HA settings are preserved on deployment. Running the HA setup helper again restarts the web service so it reloads the saved settings.
