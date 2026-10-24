# Changelog

## 0.3.0-dev - Unreleased

- Add editable unit dropdown suggestions and default new items to `stück`.
- Add a numeric value-per-unit field backed by HA `price`, with euro formatting in the overview.

- Offer existing groups and locations as editable dropdown suggestions on create and edit forms; new typed values are saved with the item.

- Add and edit items through the WebUI: name, quantity, unit, category and location.
- Save changes directly to the configured Home Assistant inventory without a separate database.
- Add signed forms, duplicate-submission protection and checks for stale edits and duplicate names.
- Verify writes by reading saved values; uncertain results are never retried automatically.
- Update the pinned LXC installer and preserve private runtime settings.
- Pass 43 automated tests and a real create/edit/rename test with temporary-item cleanup.

## 0.2.0 - 2026-10-24

- First read-only WebUI on HTTP port 80, showing the configured HA inventory.
- Automatic web service startup and prepared optional shared-password authentication.

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
