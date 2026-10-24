#!/usr/bin/env bash
# Install reviewed WebUI artifacts inside an existing Debian LXC.
set -Eeuo pipefail
[[ "$EUID" == 0 ]] || { echo 'Run as root inside the LXC.' >&2; exit 1; }
[[ "$(systemd-detect-virt --container 2>/dev/null || true)" == lxc ]] || { echo 'Expected an LXC.' >&2; exit 1; }
APP_ROOT=/opt/simpleinventory-webui
REF=fd73d3a68780083e07827dbf6c903af0e0a9797c
BASE=https://raw.githubusercontent.com/VexMex/SimpleInventory-WebUI
[[ -x "$APP_ROOT/venv/bin/python" ]] || { echo 'Run the dependency bootstrap first.' >&2; exit 1; }
stage=$(mktemp -d /tmp/simpleinventory-webui.XXXXXXXX)
cleanup() {
  rm -f -- "$stage/web.py" "$stage/__init__.py" "$stage/index.html" "$stage/login.html" "$stage/item.html" "$stage/web.service" "$stage/setup-ha.py"
  rmdir -- "$stage"
}
trap cleanup EXIT
fetch() {
  curl -fsSL --retry 3 --connect-timeout 15 --max-time 120 "$BASE/$REF/$1" -o "$stage/$2"
  printf '%s  %s\n' "$3" "$stage/$2" | sha256sum -c -
}
fetch webui/__init__.py __init__.py e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
fetch webui/web.py web.py 49819691c620fb679c3e01fd85470794c3bf694270cde31e888082f4ff888d15
fetch webui/templates/index.html index.html 076bb3678e289cae433e24f37dee9f5fa70a34a3f590ac5fd7e9e339e02bf8ba
fetch webui/templates/item.html item.html d4ab7f563386c5292a340b7e9f9b8f544fb9e68006a7e3f01bc7a24e34fef672
fetch webui/templates/login.html login.html c0005cad267992ec0a0072e54b14ee35317abd781786b653cfe131cc474c0954
fetch install/simpleinventory-web.service web.service 8e04b8b821475b24718e03f771425bb698a6ca65eed7350cbb15d6d19605005e
fetch scripts/setup_ha.py setup-ha.py 0e94e8f959d4f4fb3c5ed5850fb77950e4cc3aac2d61aeaec392605fd5dc8618
"$APP_ROOT/venv/bin/python" -c 'import fastapi,uvicorn,jinja2,websockets,itsdangerous'
release="$APP_ROOT/releases/$REF"
install -d -m 0755 "$APP_ROOT/releases" "$release" "$release/webui" "$release/webui/templates"
install -m 0644 "$stage/__init__.py" "$release/webui/__init__.py"
install -m 0644 "$stage/web.py" "$release/webui/web.py"
install -m 0644 "$stage/index.html" "$release/webui/templates/index.html"
install -m 0644 "$stage/item.html" "$release/webui/templates/item.html"
install -m 0644 "$stage/login.html" "$release/webui/templates/login.html"
# Only application code changes; never overwrite /etc/simpleinventory-webui/*.env.
install -m 0755 "$stage/setup-ha.py" "$APP_ROOT/setup-ha.py"
if ! getent group simpleinventory-webui >/dev/null; then groupadd --system simpleinventory-webui; fi
if ! id simpleinventory-webui >/dev/null 2>&1; then
  useradd --system --gid simpleinventory-webui --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin simpleinventory-webui
fi
[[ "$(id -u simpleinventory-webui)" != 0 ]] || { echo 'Refusing root service identity.' >&2; exit 1; }
if [[ -e "$APP_ROOT/current" && ! -L "$APP_ROOT/current" ]]; then
  echo 'Current application path is not a symlink; refusing to replace it.' >&2
  exit 1
fi
link="$APP_ROOT/.current-$$"
ln -s "$release" "$link"
mv -Tf "$link" "$APP_ROOT/current"
install -m 0644 "$stage/web.service" /etc/systemd/system/simpleinventory-web.service
systemd-analyze verify /etc/systemd/system/simpleinventory-web.service
systemctl daemon-reload
systemctl enable simpleinventory-web.service
systemctl restart simpleinventory-web.service
for ((attempt=0;attempt<15;attempt++)); do
  if curl -fsS --max-time 2 http://127.0.0.1/health >/dev/null; then
    printf 'WebUI ready on port 80. Private HA settings were preserved.\n'
    exit 0
  fi
  sleep 1
done
printf 'WebUI did not become ready. Check service status locally.\n' >&2
exit 1
# end
