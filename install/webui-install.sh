#!/usr/bin/env bash
# Install reviewed WebUI code; preserve private runtime settings and user defaults.
set -Eeuo pipefail
[[ "$EUID" == 0 ]] || { echo 'Run as root inside the LXC.' >&2; exit 1; }
[[ "$(systemd-detect-virt --container 2>/dev/null || true)" == lxc ]] || { echo 'Expected an LXC.' >&2; exit 1; }
APP_ROOT=/opt/simpleinventory-webui
REF=28d9ee43032cf5c758dd0c0028e0da8e33a8fece
BASE=https://raw.githubusercontent.com/VexMex/SimpleInventory-WebUI
[[ -x "$APP_ROOT/venv/bin/python" ]] || { echo 'Run the dependency bootstrap first.' >&2; exit 1; }
stage=$(mktemp -d /tmp/simpleinventory-webui.XXXXXXXX)
cleanup() {
  rm -f -- "$stage/__init__.py" "$stage/web.py" "$stage/localization.py" "$stage/preferences.py" "$stage/base.html" "$stage/styles.css" "$stage/index.html" "$stage/item.html" "$stage/login.html" "$stage/error.html" "$stage/settings.html" "$stage/settings.ini" "$stage/web.service" "$stage/setup-ha.py"
  rmdir -- "$stage"
}
trap cleanup EXIT
fetch() {
  curl -fsSL --retry 3 --connect-timeout 15 --max-time 120 "$BASE/$REF/$1" -o "$stage/$2"
  printf '%s  %s\n' "$3" "$stage/$2" | sha256sum -c -
}
fetch webui/__init__.py __init__.py e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
fetch webui/web.py web.py c5d2072c613f0e9daad5dddd5545c8d25c76dc8ae5c9a380c91d6f84bd08e58c
fetch webui/localization.py localization.py e780af022ad3c8756140e77a663550ceedd80f7ac108a7af52be08f8b27c7135
fetch webui/preferences.py preferences.py 5cad51c705820bc0156375402fae3ad49289ee498d4044d8f8b924b8bf5b3324
fetch webui/templates/base.html base.html d57b37f1262572d248bff4444630c51ddcd7ccded4fe038b6fbeb71e1adbc23e
fetch webui/templates/styles.css styles.css f2167dc6c4b3e80f8bdcfc6dba78219da228108b770b1485a8fac9cf8b51dee4
fetch webui/templates/index.html index.html 69f67241255de09cd6625415f4be9341cee53f85156392ad28d34cfe021cd35d
fetch webui/templates/item.html item.html 0851d9dab9dcb462177ca98d3c45fcfc76582ae793f2c01f74971d157fe0b01e
fetch webui/templates/login.html login.html d36bf33db106c99d0ceec2a2ea5eb6cdf0cd1809b40162b9a5b70186b01eba1d
fetch webui/templates/error.html error.html 25428f3fcf28e99715f5994805eafb41109168df07d3865dba8ac596fca25eee
fetch webui/templates/settings.html settings.html 0ac1dc061efa9d5f90e40d06a6a4794e860ea6028e966feee96829eeca4e2f90
fetch install/settings.ini settings.ini 6ed21e99166aa2f43d044393b0a1225c19f920bce2f30060daeaff26a999ef72
fetch install/simpleinventory-web.service web.service e0701d656c664ae6c3001ba458e21b283e55f5159134cbefd1e17a312bc062b0
fetch scripts/setup_ha.py setup-ha.py 0e94e8f959d4f4fb3c5ed5850fb77950e4cc3aac2d61aeaec392605fd5dc8618
"$APP_ROOT/venv/bin/python" -c 'import fastapi,uvicorn,jinja2,websockets,itsdangerous'
release="$APP_ROOT/releases/$REF"
install -d -m 0755 "$APP_ROOT/releases" "$release" "$release/webui" "$release/webui/templates"
install -m 0644 "$stage/__init__.py" "$release/webui/__init__.py"
install -m 0644 "$stage/web.py" "$release/webui/web.py"
install -m 0644 "$stage/localization.py" "$release/webui/localization.py"
install -m 0644 "$stage/preferences.py" "$release/webui/preferences.py"
install -m 0644 "$stage/base.html" "$release/webui/templates/base.html"
install -m 0644 "$stage/styles.css" "$release/webui/templates/styles.css"
install -m 0644 "$stage/index.html" "$release/webui/templates/index.html"
install -m 0644 "$stage/item.html" "$release/webui/templates/item.html"
install -m 0644 "$stage/login.html" "$release/webui/templates/login.html"
install -m 0644 "$stage/error.html" "$release/webui/templates/error.html"
install -m 0644 "$stage/settings.html" "$release/webui/templates/settings.html"
install -m 0755 "$stage/setup-ha.py" "$APP_ROOT/setup-ha.py"
install -d -m 0700 /etc/simpleinventory-webui
if [[ -e /etc/simpleinventory-webui/settings.ini || -L /etc/simpleinventory-webui/settings.ini ]]; then
  [[ -f /etc/simpleinventory-webui/settings.ini && ! -L /etc/simpleinventory-webui/settings.ini ]] || { echo 'Unsafe settings path.' >&2; exit 1; }
  [[ "$(stat -c %u /etc/simpleinventory-webui/settings.ini)" == 0 ]] || { echo 'Settings must belong to root.' >&2; exit 1; }
else
  install -m 0600 "$stage/settings.ini" /etc/simpleinventory-webui/settings.ini
fi
"$APP_ROOT/venv/bin/python" -c 'import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from webui.preferences import InstallationSettings;InstallationSettings.read(Path("/etc/simpleinventory-webui/settings.ini"))' "$release"
if ! getent group simpleinventory-webui >/dev/null; then groupadd --system simpleinventory-webui; fi
if ! id simpleinventory-webui >/dev/null 2>&1; then
  useradd --system --gid simpleinventory-webui --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin simpleinventory-webui
fi
[[ "$(id -u simpleinventory-webui)" != 0 ]] || { echo 'Refusing root service identity.' >&2; exit 1; }
if [[ -e "$APP_ROOT/current" && ! -L "$APP_ROOT/current" ]]; then
  echo 'Current application path is not a symlink; refusing to replace it.' >&2
  exit 1
fi
systemd-analyze verify "$stage/web.service"
link="$APP_ROOT/.current-$$"
ln -s "$release" "$link"
mv -Tf "$link" "$APP_ROOT/current"
install -m 0644 "$stage/web.service" /etc/systemd/system/simpleinventory-web.service
systemctl daemon-reload
systemctl enable simpleinventory-web.service
systemctl restart simpleinventory-web.service
for ((attempt=0;attempt<15;attempt++)); do
  if curl -fsS --max-time 2 http://127.0.0.1/health >/dev/null; then
    printf 'WebUI ready on port 80. Existing private settings and INI defaults were preserved.\n'
    exit 0
  fi
  sleep 1
done
printf 'WebUI did not become ready. Check service status locally.\n' >&2
exit 1
# end
