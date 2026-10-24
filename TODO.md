# Ideas and future work

Version 0.3.0 is the functional baseline for the agreed initial scope. This is an idea backlog, not a committed roadmap: items have no promised implementation date or release. Check feasibility and agree on scope before implementation.

## Language and localization

- [ ] Add translations and automatically use the Home Assistant system language as the initial default.
- [ ] Offer a manual language override in settings.
- [ ] Localize number, currency and date formatting.

## Settings and appearance

- [ ] Add settings for currency display, language, styles, themes and password behavior.
- [ ] Define where installation-wide settings and individual display preferences are stored.
- [ ] Build a consistent visual design for the overview, forms, settings and feedback messages.
- [ ] Add light mode, dark mode and an option to follow the device preference.
- [ ] Keep currency selection a display preference unless currency conversion is explicitly added; do not imply that changing a symbol converts stored values.

## Authentication and external access

- [ ] Review and test password behavior for local-network and external clients.
- [ ] Test with actual internet access and an external IP, in an explicitly authorized test environment.
- [ ] Cover different private subnets, IPv4/IPv6, VPNs and reverse proxies; verify that forwarded headers cannot grant unintended local bypass.
- [ ] Make password configuration and local-network bypass behavior understandable in settings.
- [ ] Review HTTPS, session expiry and login rate limits before supporting external access.

## Mobile usability and accessibility

- [ ] Make the interface work well on phones and tablets, including narrow inventory tables and forms.
- [ ] Improve touch targets, virtual-keyboard behavior and navigation on small screens.
- [ ] Check keyboard navigation, screen-reader labels, contrast and visible focus indicators.

## Optional application packaging

- [ ] Evaluate an Android smartphone app.
- [ ] Evaluate an installable web app (PWA) as an alternative to maintaining a separate Android app; define behavior when Home Assistant is unavailable.
- [ ] Evaluate packaging as a Home Assistant app (add-on), as an optional alternative to the Proxmox LXC installation.
- [ ] Investigate Home Assistant ingress, authentication and update requirements for that packaging option.

## Additional ideas to consider

- [ ] Add item search, sorting and filters for group and location.
- [ ] Show an optional inventory-value total with clear quantity-times-value-per-unit semantics.
- [ ] Improve connection status, last-refresh information and recovery messages when Home Assistant is unavailable.
- [ ] Add unsaved-change warnings and preserve form input after validation errors.
- [ ] Provide a documented update and rollback command that preserves private settings.
- [ ] Evaluate CSV export of the selected inventory.
- [ ] Evaluate item deletion with explicit confirmation and investigate recovery support first.
- [ ] Consider barcode/QR scanning only if it improves the intended simple inventory workflow.

## Existing project boundaries

- Home Assistant remains the source of truth for inventory data.
- Inventory creation, renaming and deletion remain in Home Assistant.
- Real credentials stay local to the installation and outside the repository; future settings and packaging must preserve this boundary.
