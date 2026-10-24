# Changelog

## 0.3.0 - 2026-10-24

Functional WebUI baseline for the agreed initial feature scope.

- Create and edit items: name, quantity, unit, value per unit, group and location.
- Offer editable dropdown suggestions for units, groups and locations; save new typed values with the item.
- Default new items to the unit `stück` and display euro values in the overview.
- Discover existing inventories, select the alphabetically first by default and switch using a dropdown.
- Keep selections in the URL and bind item forms to their original inventory across browser tabs.
- Simplify HA setup by removing fixed inventory selection; retain compatibility with existing local settings.
- Save through HA without a separate database; leave inventory administration in Home Assistant.
- Protect saves with signed forms, duplicate-submission and stale-edit checks, duplicate-name checks and post-save verification.
- Update the pinned installer while preserving private runtime settings.
- Validate with 50 automated tests, live item create/edit/rename tests and real HA discovery and connection checks.

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
