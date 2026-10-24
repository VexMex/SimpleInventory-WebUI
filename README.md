# SimpleInventory-WebUI

A planned Python web interface for the Simple Inventory integration in Home Assistant.

## Current state

This repository currently contains the installation foundation and credential policy, not a working WebUI. Existing LICENSE is retained. No Home Assistant instance has been configured, and no LXC is created by this installer.

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
- itsdangerous: signed session support; complete authentication and CSRF handling still need implementation.
- systemd (provided by the Debian container): eventual service startup and restart.

Initial UI scope: list inventories; search/filter items by category and location; create/edit items; increment/decrement quantities; confirm deletion; display successful or failed saves. The backend must reconcile uncertain write results instead of blindly retrying.

## Proxmox foundation

Suggested starting allocation (not a benchmark): unprivileged Debian 13 LXC, 1 vCPU, 1 GB RAM, 4 GB disk; DHCP initially. Debian 12 is also accepted but has not been tested here.

On the tested Proxmox/Debian 13 combination, systemd 257 required the Proxmox LXC feature nesting=1. Without it, tmp.mount, run-lock.mount and dev-mqueue.mount failed. Enabling nesting and restarting the new container resolved all three failures. This application does not require Docker, GPU passthrough or a privileged container.

The Community Scripts pattern separates host-side container creation from inside-container application installation. install/bootstrap-lxc.sh implements only the second part for dependency preparation and deliberately refuses the Proxmox host.

The repository is public. No GitHub login or token is needed for installation. Run the following as root INSIDE an existing target Debian LXC:

```bash
revision=c11eecb5e867f0841e5bde1fa1c6d8702a8ecbec
apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && curl -fsSL --retry 3 --connect-timeout 15 \
     "https://raw.githubusercontent.com/VexMex/SimpleInventory-WebUI/${revision}/install/bootstrap-lxc.sh" \
     -o /root/simpleinventory-bootstrap.sh \
  && bash /root/simpleinventory-bootstrap.sh
```

The URL pins the tested installer revision. A fresh Debian template may not contain curl, so its installation comes first. For controlled upgrades, review and select a newer revision rather than silently executing a changing branch.

The bootstrap installs Python, an isolated virtual environment and the intended Python dependencies. It does not create an LXC, install a database, run a full OS upgrade, change firewall rules, request credentials or start an application service. Re-running may resolve newer Python package versions within the initial development constraints; package versions and hashes must be locked before a production deployment.

Test results: [Debian 13 LXC bootstrap](docs/bootstrap-test.md).

A future host-side LXC creator and application installer can provide a complete one-command flow. They are not implemented yet.

## Credentials

Read SECURITY.md and AGENTS.md before changing or uploading anything. Real credentials never belong on GitHub. The user permits local runtime storage in the installation LXC: /etc/simpleinventory-webui/app.env, outside the source tree, owned by root with mode 0600. Configuration and login functionality still need implementation.

References:
- https://github.com/blaineventurine/simple_inventory
- https://github.com/community-scripts/ProxmoxVE/blob/main/ct/homebox.sh
- https://github.com/community-scripts/ProxmoxVE/blob/main/install/homebox-install.sh
- https://fastapi.tiangolo.com/
