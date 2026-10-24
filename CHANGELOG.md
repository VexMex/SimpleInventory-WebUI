# Changelog

## 0.1.0 - 2026-10-24

First tested infrastructure and Home Assistant connection baseline.

- One-command Proxmox installer creates a new Debian 13 unprivileged LXC.
- Interactive resource, storage and network choices; occupied IDs are rejected.
- Direct root shell through the authenticated Proxmox console.
- Python dependency foundation and manually executed HA setup helper.
- Hidden long-lived token input, read-only inventory verification and protected local settings.
- Saved credentials are reused for later connections and checked at boot.
- Offline credential scanning before repository uploads.
- Installer and synthetic connection tests passed; a real configured HA inventory was read successfully.

This is an early baseline. The browser WebUI, application login and full inventory editing interface are not implemented yet.
