# Manual Home Assistant connection

After LXC creation, open Console in the Proxmox web interface. The installer configures a direct root shell (console mode shell), so no guest login password is needed. Run:

```bash
/usr/local/bin/simpleinventory-setup
```

The installer downloads this helper and its boot check automatically, but never starts the interactive login setup. It verifies their SHA-256 checksums before creating the LXC.

The helper asks for the HA base URL, a long-lived access token (hidden input), and an existing Simple Inventory inventory. It reads the item list to confirm API access before saving. It does not test write access or change inventory data.

For plain HTTP, it explains that the token crosses the network unencrypted and requires an explicit choice. HTTPS uses normal certificate verification; there is no TLS-bypass option. Proxy environment variables are not used for this connection.

## Creating a token

A separate HA account is optional, but a dedicated non-administrator service user is recommended.

1. As HA administrator, open Settings > People > Users and create a user, for example simpleinventory-webui, with Administrator disabled.
2. Sign into HA as that new user in a separate browser profile or private window.
3. Open that user's profile > Security > Long-lived access tokens and create a token for this application.
4. Paste the token only into the hidden prompt in the LXC console. Never send it in chat, GitHub, a command argument or a URL.

The helper stores no HA account password. It authenticates using the manually provided token. HA documents these tokens as valid for ten years; they can be revoked earlier.

## Permission limitations

HA does not provide a normal user-setting scope restricting this token exclusively to Simple Inventory. Non-admin removes administration privileges, but is not an inventory-only permission boundary. The built-in Users group can also read/control other entities.

The reviewed Simple Inventory v0.6.0 WebSocket implementation does not implement a per-user inventory allowlist. Selecting an inventory in this setup configures application behavior, not HA authorization. Dashboard visibility is not API authorization either. Strict inventory-only access would require an additional gateway with enforced command rules or changes to the HA integration, beyond this setup.

References:
- https://www.home-assistant.io/docs/configuration/user-configuration/
- https://contributors.home-assistant.io/core/internals/auth-api/
- https://contributors.home-assistant.io/core/internals/permissions/
- https://github.com/blaineventurine/simple_inventory/blob/v0.6.0/custom_components/simple_inventory/websocket_api.py

## Local persistence and reboot

Private settings are saved atomically to /etc/simpleinventory-webui/app.env. Directory mode: 0700. File mode: 0600, root-owned. Updates to application code do not replace this file.

Existing configuration requires confirmation before replacement. Input, authentication or inventory-query failure leaves the existing file untouched. Token values and remote exception bodies are not printed.

The installed and enabled simpleinventory-ha-check.service reads the saved settings after network startup and performs a read-only API check. If no configuration exists yet, the check is skipped. On failure it retries after 30 seconds. A successful check stays active (exited); it is not a persistent WebSocket session or a running WebUI.

Manual check:

```bash
/usr/local/bin/simpleinventory-setup --check
```

A restart does not require entering the token again. Revoking/expiring the token, disabling/deleting the HA user, changing the HA URL or removing the inventory may require reconfiguration.

The eventual WebUI must reuse this configuration loader and reconnect with the stored token. The WebUI service itself has not been implemented yet.

## Validation

Nine automated tests with synthetic tokens and a local simulated HA server passed in the Debian 13 test LXC: protected file roundtrip, unsafe permissions and symlink rejection, failed validation preserving prior settings, unsafe URL rejection, explicit HTTP choice, repeated connections using saved settings, auth failure redaction, and API failure redaction. No real HA token was used in these tests.

The helper and enabled systemd unit were also installed in the existing test LXC. The absolute command path and systemd unit validation passed. With no private configuration present, the boot-check condition correctly skips the service. No real HA login or reboot with a real token has been tested.
