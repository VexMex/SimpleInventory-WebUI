# Bootstrap test: Debian 13 LXC

Date: 2026-10-24

## Scope and result

PASS: install/bootstrap-lxc.sh from revision c11eecb5e867f0841e5bde1fa1c6d8702a8ecbec was downloaded anonymously from public GitHub and executed successfully in a newly created unprivileged LXC. This validates dependency installation, not a working inventory application.

Environment: Proxmox VE 9.1.11, Debian 13 amd64 template, 1 vCPU, 1 GB RAM, 256 MB swap, 4 GB root disk. No GPU passthrough or Docker.

## Findings

- Fresh Debian template had no curl. Install ca-certificates and curl before attempting the GitHub download.
- systemd 257 initially failed tmp.mount, run-lock.mount and dev-mqueue.mount with nesting disabled.
- Enabling the Proxmox LXC feature nesting=1 and restarting this new container resolved those failures. Final systemd state: running; zero failed units.
- The template emitted locale warnings; package installation still completed successfully.

## Checks performed

- Public HTTPS download without GitHub credentials: passed.
- Bash syntax check of the downloaded script: passed.
- Bootstrap process exit code: 0.
- Python 3.13 virtual environment creation: passed.
- pip check: No broken requirements found.
- Import check for all eight directly requested Python packages: passed.

Direct Python package versions resolved in this test:

| Package | Version |
| --- | --- |
| fastapi | 0.162.0 |
| uvicorn | 0.54.0 |
| Jinja2 | 3.1.6 |
| httpx | 0.28.1 |
| websockets | 16.1.1 |
| python-multipart | 0.0.32 |
| pydantic-settings | 2.16.1 |
| itsdangerous | 2.2.0 |

The installer currently uses development version ranges. A pinned installer revision does not pin packages obtained from PyPI. A production release still requires tested dependency locking with hashes.

## Credential audit

All seven repository files and the two existing commit messages were reviewed and scanned using the repository's offline Secret Guard before documenting the result. The earlier commit contains only the same LICENSE retained in the current tree. No credential findings were detected.

No Home Assistant token, application password or private runtime configuration was supplied during this test. No local access notes, private keys, raw logs, host addresses or other project files are part of this report.

## Remaining scope

The WebUI, HA adapter, authentication, systemd application service and Proxmox host-side container creator are not implemented in this bootstrap. No application endpoint or inventory operation was tested.
