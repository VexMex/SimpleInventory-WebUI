#!/usr/bin/env bash
# Creates a NEW LXC on a Proxmox host. Never replaces existing guests.
set -Eeuo pipefail
CT_CREATED=0
BOOTSTRAP_FILE=
CTID=
cleanup() {
  if [[ -n "$BOOTSTRAP_FILE" && -f "$BOOTSTRAP_FILE" ]]; then rm -f -- "$BOOTSTRAP_FILE"; fi
}
failed() {
  printf '\nInstallation failed at line %s.\n' "$1" >&2
  if [[ "$CT_CREATED" == 1 ]]; then printf 'New LXC %s was kept for diagnosis.\n' "$CTID" >&2; fi
}
trap cleanup EXIT
trap 'failed "$LINENO"' ERR
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
[[ "$EUID" == 0 ]] || die 'Run as root in the Proxmox HOST shell.'
for tool in pveversion pct pvesh pvesm pveam curl ip awk sort sha256sum; do
  command -v "$tool" >/dev/null || die "Missing host command: $tool"
done
[[ "$(dpkg --print-architecture)" == amd64 ]] || die 'Currently supports amd64 only.'
[[ ! -e /run/systemd/container ]] || die 'Run on the Proxmox host, not in a container.'

# Immutable, reviewed guest bootstrap and its checksum.
BOOTSTRAP_REV=c11eecb5e867f0841e5bde1fa1c6d8702a8ecbec
BOOTSTRAP_SHA=5bcd879eee26b79a91b44517fb514a733c1abb9bc43438d1043a58842e7dae8f
REPOSITORY=https://raw.githubusercontent.com/VexMex/SimpleInventory-WebUI
storage_available() {
  pvesm status --content "$2" | awk -v wanted="$1" 'NR>1 && $1==wanted && $3=="active" {found=1} END {exit !found}'
}
first_storage() {
  pvesm status --content "$1" | awk 'NR>1 && $3=="active" {print $1; exit}'
}
suggested_root=$(first_storage rootdir)
if storage_available local-lvm rootdir; then suggested_root=local-lvm; fi
suggested_template=$(first_storage vztmpl)
[[ -n "$suggested_root" && -n "$suggested_template" ]] || die 'Need active rootdir and template storage.'
suggested_bridge=$(ip -o link show type bridge | awk -F': ' '{print $2; exit}')
if ip link show vmbr0 >/dev/null 2>&1; then suggested_bridge=vmbr0; fi
[[ -n "$suggested_bridge" ]] || die 'No network bridge found.'
CTID=${SIW_CTID:-$(pvesh get /cluster/nextid)}
CT_NAME=${SIW_HOSTNAME:-simpleinventory-webui}
ROOT_STORAGE=${SIW_STORAGE:-$suggested_root}
TEMPLATE_STORAGE=${SIW_TEMPLATE_STORAGE:-$suggested_template}
BRIDGE=${SIW_BRIDGE:-$suggested_bridge}
CORES=${SIW_CORES:-1}
MEMORY=${SIW_MEMORY:-1024}
DISK=${SIW_DISK:-4}
NONINTERACTIVE=${SIW_NONINTERACTIVE:-0}
[[ "$NONINTERACTIVE" == 0 || "$NONINTERACTIVE" == 1 ]] || die 'Invalid SIW_NONINTERACTIVE.'
prompt() {
  local name=$1 label=$2 answer
  read -r -p "$label [${!name}]: " answer </dev/tty
  if [[ -n "$answer" ]]; then printf -v "$name" '%s' "$answer"; fi
}
printf '\nSimpleInventory-WebUI - Proxmox LXC setup\n'
printf 'Current scope: Python foundation; the WebUI is not implemented yet.\n'
if [[ "$NONINTERACTIVE" == 0 ]]; then
  [[ -r /dev/tty && -w /dev/tty ]] || die 'Interactive terminal required.'
  prompt CTID 'Container ID'
  prompt CT_NAME 'Hostname'
  prompt ROOT_STORAGE 'Root disk storage'
  prompt TEMPLATE_STORAGE 'Template storage'
  prompt BRIDGE 'Network bridge'
  prompt CORES 'CPU cores'
  prompt MEMORY 'Memory in MB'
  prompt DISK 'Disk size in GB'
fi
[[ "$CTID" =~ ^[1-9][0-9]{2,8}$ ]] || die 'Invalid container ID.'
[[ "$CT_NAME" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]] || die 'Invalid hostname.'
[[ "$ROOT_STORAGE" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || die 'Invalid storage name.'
[[ "$TEMPLATE_STORAGE" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || die 'Invalid template storage.'
[[ "$BRIDGE" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || die 'Invalid bridge.'
[[ "$CORES" =~ ^[1-9][0-9]{0,2}$ ]] || die 'Invalid core count.'
[[ "$MEMORY" =~ ^[1-9][0-9]{2,6}$ ]] && (( MEMORY >= 512 )) || die 'Memory must be at least 512 MB.'
[[ "$DISK" =~ ^[1-9][0-9]{0,2}$ ]] && (( DISK >= 4 )) || die 'Disk must be at least 4 GB.'
storage_available "$ROOT_STORAGE" rootdir || die 'Root disk storage unavailable.'
storage_available "$TEMPLATE_STORAGE" vztmpl || die 'Template storage unavailable.'
ip -o link show type bridge | awk -F': ' -v b="$BRIDGE" '$2==b {found=1} END {exit !found}' || die 'Selected bridge does not exist.'
pvesh get /cluster/nextid --vmid "$CTID" >/dev/null
printf '\nNew LXC %s (%s): Debian 13, unprivileged, nesting enabled.\n' "$CTID" "$CT_NAME"
printf '%s core(s), %s MB RAM, %s GB disk on %s; DHCP on %s.\n' "$CORES" "$MEMORY" "$DISK" "$ROOT_STORAGE" "$BRIDGE"
printf 'Automatic host-boot startup: disabled.\n'
if [[ "$NONINTERACTIVE" == 0 ]]; then
  read -r -p 'Create this LXC and install dependencies? [y/N]: ' answer </dev/tty
  [[ "$answer" == y || "$answer" == Y ]] || { printf 'Cancelled; no LXC created.\n'; exit 0; }
fi

# Verify the installer before allocating a guest.
BOOTSTRAP_FILE=$(mktemp /tmp/simpleinventory-bootstrap.XXXXXXXX.sh)
curl -fsSL --retry 3 --connect-timeout 15 --max-time 120 \
  "$REPOSITORY/$BOOTSTRAP_REV/install/bootstrap-lxc.sh" -o "$BOOTSTRAP_FILE"
printf '%s  %s\n' "$BOOTSTRAP_SHA" "$BOOTSTRAP_FILE" | sha256sum -c -
bash -n "$BOOTSTRAP_FILE"
pveam update
TEMPLATE=$(pveam available --section system | awk '$2 ~ /^debian-13-standard_.*_amd64\.tar\.zst$/ {print $2}' | sort -V | tail -n 1)
[[ -n "$TEMPLATE" ]] || die 'No Debian 13 amd64 template found.'
if ! pveam list "$TEMPLATE_STORAGE" | awk -v name="$TEMPLATE_STORAGE:vztmpl/$TEMPLATE" '$1==name {found=1} END {exit !found}'; then
  pveam download "$TEMPLATE_STORAGE" "$TEMPLATE"
fi
pvesh get /cluster/nextid --vmid "$CTID" >/dev/null
pct create "$CTID" "$TEMPLATE_STORAGE:vztmpl/$TEMPLATE" \
  --hostname "$CT_NAME" --ostype debian --unprivileged 1 --features nesting=1 \
  --cores "$CORES" --memory "$MEMORY" --swap 256 --rootfs "$ROOT_STORAGE:$DISK" \
  --net0 "name=eth0,bridge=$BRIDGE,ip=dhcp,type=veth,firewall=1" \
  --onboot 0 --description 'SimpleInventory-WebUI dependency foundation; HA not configured'
CT_CREATED=1
pct start "$CTID"
pct push "$CTID" "$BOOTSTRAP_FILE" /root/simpleinventory-bootstrap.sh --perms 0700
ready=0
for ((attempt=0; attempt<60; attempt++)); do
  if pct exec "$CTID" -- bash -c 'ip -4 route show default | grep -q . && getent ahostsv4 deb.debian.org >/dev/null'; then
    ready=1
    break
  fi
  sleep 2
done
[[ "$ready" == 1 ]] || die "LXC $CTID has no working DHCP/DNS after 120 seconds."
pct exec "$CTID" -- env LC_ALL=C.UTF-8 bash /root/simpleinventory-bootstrap.sh
printf '\nSUCCESS: LXC %s (%s) is prepared.\n' "$CTID" "$CT_NAME"
pct exec "$CTID" -- ip -4 -brief address show eth0
printf 'Python: /opt/simpleinventory-webui/venv\n'
printf 'No WebUI service or HA credentials are configured yet.\n'
# end
