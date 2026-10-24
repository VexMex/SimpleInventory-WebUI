#!/usr/bin/env bash
# Dependency foundation only: no application service and no credentials.
set -Eeuo pipefail
trap 'printf "Installation failed at line %s. No credentials were requested.\n" "$LINENO" >&2' ERR

if [[ "${EUID}" -ne 0 ]]; then
  printf 'Run this script as root inside the target LXC.\n' >&2
  exit 1
fi
if command -v pveversion >/dev/null 2>&1; then
  printf 'Refusing to run on the Proxmox host. Open the target LXC console.\n' >&2
  exit 1
fi
if [[ ! -r /etc/os-release ]]; then
  printf 'Cannot identify the operating system.\n' >&2
  exit 1
fi
. /etc/os-release
if [[ "${ID:-}" != debian || ( "${VERSION_ID:-}" != 12 && "${VERSION_ID:-}" != 13 ) ]]; then
  printf 'Supported foundation: Debian 12 or 13 LXC.\n' >&2
  exit 1
fi
if [[ "$(systemd-detect-virt --container 2>/dev/null || true)" != lxc ]]; then
  printf 'Expected an LXC container. No changes made.\n' >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl python3 python3-venv

APP_ROOT=/opt/simpleinventory-webui
VENV="$APP_ROOT/venv"
install -d -m 0755 "$APP_ROOT"
if [[ ! -e "$VENV" ]]; then
  python3 -m venv "$VENV"
elif [[ ! -x "$VENV/bin/python" ]]; then
  printf 'Existing venv path is invalid; refusing to overwrite it.\n' >&2
  exit 1
fi

# Initial development constraints; a tested, hash-locked release is required
# before the actual application is deployed.
"$VENV/bin/python" -m pip --isolated install --index-url https://pypi.org/simple \
  'fastapi>=0.115,<1' 'uvicorn>=0.30,<1' 'Jinja2>=3.1.6,<4' \
  'httpx>=0.28,<1' 'websockets>=14,<17' 'python-multipart>=0.0.20,<1' \
  'pydantic-settings>=2.6,<3' 'itsdangerous>=2.2,<3'
"$VENV/bin/python" -m pip check
"$VENV/bin/python" - <<'PY'
import fastapi, uvicorn, jinja2, httpx, websockets
import python_multipart, pydantic_settings, itsdangerous
print("Python dependencies imported successfully.")
PY
printf '\nFoundation ready in %s.\n' "$APP_ROOT"
printf 'No WebUI is running yet; no network port or HA connection was opened.\n'
