# Version 0.1.0 baseline

The VERSION file and v0.1.0 Git tag identify the first tested installation and HA connection baseline. Keep published version tags at their original commits; subsequent development belongs on main and gets a new version when ready.

To install this source baseline on a Proxmox host:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/VexMex/SimpleInventory-WebUI/v0.1.0/install.sh)"
```

This creates a NEW LXC. It is not an in-place downgrade command.

A tag preserves repository source, not the entire operating system or package repositories. Python packages in the current bootstrap still use development version ranges. New installations at a later date may resolve different package versions even with this tag. Guest bootstrap and HA setup artifacts themselves are already pinned to reviewed revisions and checksums.

For the exact working test environment, a separate local Proxmox LXC snapshot named siw-v0-1-0 is retained. Its private runtime settings, including the configured HA token, stay on the local virtualization storage and are never uploaded to GitHub.

Restoring that snapshot would revert container files and configuration to the saved state. It would not rewind inventory records stored in Home Assistant. Snapshot restoration must be requested explicitly before it is performed.

The WebUI is not implemented at version 0.1.0. See CHANGELOG.md for included functionality.
