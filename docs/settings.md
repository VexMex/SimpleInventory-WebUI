# Localization and display settings

## Installation-wide defaults

The installation creates /etc/simpleinventory-webui/settings.ini, owned by root with mode 0600. It is separate from application code and private HA settings. The installer preserves an existing file.

Edit the INI file from the LXC root console, then restart:

```bash
systemctl restart simpleinventory-web.service
```

Supported settings:

```ini
[display]
language = auto
currency = EUR
theme = auto
accent = teal
density = comfortable

[access]
enabled = false
local_bypass = true
```

- language: auto, de or en. Auto follows the HA system language from get_config, not the individual HA user's profile language.
- currency: EUR, USD, GBP or CHF.
- theme: auto follows the device preference; light and dark override it.
- accent: teal or blue.
- density: comfortable or compact.
- access.enabled: whether the existing shared-password authentication is required.
- access.local_bypass: whether directly connected private IPv4 networks and loopback may bypass that password.

Only German and English are currently translated. Other HA languages fall back to German. HA language and time zone are cached for five minutes; a failed refresh keeps the last known values and retries after 30 seconds. A new process without HA configuration falls back to German and UTC. Inventory names, item names, units, groups and locations are user data and are never translated.

Currency selection affects formatting only. It does not convert or modify HA price values. Prices remain numeric in HA and in the JSON API. The overview formats quantities and money for the selected language; the last-loaded timestamp uses the HA time zone.

## Private settings and service access

HA credentials remain in app.env; existing optional authentication credentials remain in web.env. No credentials belong in settings.ini.

The web service runs as its existing non-root account. systemd reads settings.ini as a service credential named ui-settings and supplies a private read-only copy through CREDENTIALS_DIRECTORY. The protected configuration directory does not become readable to the service account or other users. Editing the original INI requires restarting the service to load the new copy.

SIW_AUTH_ENABLED and SIW_LOCAL_BYPASS in web.env override INI access defaults for compatibility. Enabling password protection still requires a valid locally configured SIW_PASSWORD_HASH and SIW_SESSION_SECRET in web.env. Missing or invalid authentication configuration fails closed. The settings page reports the effective password policy but does not change credentials or installation-wide policy. A guided password-setup flow remains future work.

## Preferences for each browser

Open /settings to override language, currency, appearance, accent and spacing for the current browser. Installation default means that option follows settings.ini. Auto language follows HA; auto appearance follows the device.

Preferences are stored in the siw_preferences cookie for up to one year. The cookie contains only validated display choices, uses HttpOnly and SameSite=Strict, and uses Secure when served through HTTPS. Clearing browser data removes the overrides. Use installation defaults removes the cookie.

Cookie content is not an authorization source. Authentication settings, HA credentials and inventory data are never stored in the preference cookie. Settings submissions require an expiring, cookie-bound form proof. Display cookies cannot alter password requirements or local-network bypass.

The preference order is: browser override, installation default, then the documented fallback. The settings page shows the effective central password policy and the central display defaults. Saving browser preferences does not modify any INI or environment file.

## Appearance and validation

The overview, item form, login, settings and error pages share one layout and translation catalogue. Light/dark device preferences, teal/blue accents and comfortable/compact spacing are supported. Narrow screens use stacked forms and inventory cards. No remote fonts, scripts or styles are loaded.

58 automated tests passed, including the previous inventory and authentication coverage, browser isolation, preference persistence/reset, INI validation, authentication failure behavior, English feedback, and localized number/currency/date formatting.

The updated service and systemd credential loading were checked in the existing Debian LXC. Browser checks covered automatic HA language, English and USD display, light/blue appearance, return to defaults, and narrow/wider layouts. Existing private HA configuration was verified unchanged. Internet/external-IP authentication testing remains a separate TODO; this change does not expose the service externally.
