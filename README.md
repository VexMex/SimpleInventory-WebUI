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

Suggested starting allocation (not a benchmark): unprivileged Debian 13 LXC, 1 vCPU, 512 MB to 1 GB RAM, 4 GB disk; DHCP initially. Debian 12 is also accepted. No Docker nesting or privileged container is needed.

The Community Scripts pattern separates host-side container creation from inside-container application installation. install/bootstrap-lxc.sh implements only the second part for dependency preparation and deliberately refuses the Proxmox host.

Repository is currently private. An anonymous raw GitHub curl command will not work. Do not publish the repository or put a GitHub token into a command just to install it.

1. Download install/bootstrap-lxc.sh from GitHub using your authenticated browser on your own computer.
2. Copy the script to the Proxmox host, then transfer it to an existing target LXC using pct push.
3. In the Proxmox host shell, replace 123 with the actual target CT ID:

    pct push 123 /root/bootstrap-lxc.sh /root/bootstrap-lxc.sh
    pct exec 123 -- bash /root/bootstrap-lxc.sh

Alternatively paste the script into the target container console and run it there as root.

It installs Python, an isolated virtual environment and the intended Python dependencies. It does not install a database, run an OS upgrade, change firewall rules, request credentials or start a service. Re-running validates the environment and may resolve newer package versions within the initial development constraints. Before a production deployment, dependency versions and hashes must be locked and tested.

For a future public release, a host-side LXC creator and version-pinned application installer can provide a one-command flow. They are not implemented yet. Private release delivery will need an authenticated download on the user's PC or another explicitly approved approach.

## Credentials

Read SECURITY.md and AGENTS.md before changing or uploading anything. Real credentials never belong on GitHub. The user permits local runtime storage in the installation LXC: /etc/simpleinventory-webui/app.env, outside the source tree, owned by root with mode 0600. Configuration and login functionality still need implementation.

References:
- https://github.com/blaineventurine/simple_inventory
- https://github.com/community-scripts/ProxmoxVE/blob/main/ct/homebox.sh
- https://github.com/community-scripts/ProxmoxVE/blob/main/install/homebox-install.sh
- https://fastapi.tiangolo.com/
