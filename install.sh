#!/usr/bin/env bash
set -euo pipefail

UUID="google-messages@juanton.local"
APP_ID="org.juanton.MessagesGnome"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
APP_DIR="${DATA_HOME}/messages-gnome"
EXT_DIR="${DATA_HOME}/gnome-shell/extensions/${UUID}"
ICON_DIR="${DATA_HOME}/icons/hicolor"
DESKTOP_DIR="${DATA_HOME}/applications"
DBUS_DIR="${DATA_HOME}/dbus-1/services"

echo "Stopping the KDE Messages client if it is running"
pkill -f "${DATA_HOME}/messages-kde/messages-kde" 2>/dev/null || true
pkill -f "${BIN_DIR}/messages-kde" 2>/dev/null || true
sleep 0.6

if [[ -x "${HOME}/messages-kde/uninstall.sh" ]]; then
  echo "Removing the installed KDE Messages app"
  "${HOME}/messages-kde/uninstall.sh" --purge || true
elif [[ -x "${BIN_DIR}/messages-kde" ]]; then
  /bin/rm -f "${BIN_DIR}/messages-kde" "${HOME}/bin/messages-kde"
  /bin/rm -rf "${DATA_HOME}/messages-kde"
  /bin/rm -f "${DATA_HOME}/applications/org.juanton.messages-kde.desktop"
fi

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${EXT_DIR}" "${DESKTOP_DIR}" "${DBUS_DIR}" \
  "${ICON_DIR}/scalable/apps" \
  "${ICON_DIR}/symbolic/apps"

echo "Installing Google Messages helper from ${ROOT}"
mkdir -p "${APP_DIR}/messages_gnome"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  "${ROOT}/app/messages_gnome/" "${APP_DIR}/messages_gnome/"
install -m 0755 "${ROOT}/app/messages-gnome" "${APP_DIR}/messages-gnome"

cat > "${BIN_DIR}/messages-gnome" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${APP_DIR}\${PYTHONPATH:+:\${PYTHONPATH}}"
exec /usr/bin/python3 "${APP_DIR}/messages-gnome" "\$@"
EOF
chmod 0755 "${BIN_DIR}/messages-gnome"

if [[ -d "${HOME}/bin" ]]; then
  ln -sfn "${BIN_DIR}/messages-gnome" "${HOME}/bin/messages-gnome"
fi

install -m 0644 "${ROOT}/extension/icons/google-messages.svg" \
  "${ICON_DIR}/scalable/apps/${APP_ID}.svg"
install -m 0644 "${ROOT}/extension/icons/google-messages-symbolic.svg" \
  "${ICON_DIR}/symbolic/apps/${APP_ID}-symbolic.svg"

desktop_src="${ROOT}/app/data/${APP_ID}.desktop"
desktop_dst="${DESKTOP_DIR}/${APP_ID}.desktop"
sed "s|Exec=messages-gnome|Exec=${BIN_DIR}/messages-gnome|g; s|TryExec=messages-gnome|TryExec=${BIN_DIR}/messages-gnome|" \
  "${desktop_src}" > "${desktop_dst}"
chmod 0644 "${desktop_dst}"

cat > "${DBUS_DIR}/${APP_ID}.service" <<EOF
[D-BUS Service]
Name=${APP_ID}
Exec=${BIN_DIR}/messages-gnome --gapplication-service
EOF

echo "Installing GNOME Shell extension ${UUID}"
rsync -a --delete \
  --exclude '__pycache__/' \
  "${ROOT}/extension/" "${EXT_DIR}/"
glib-compile-schemas "${EXT_DIR}/schemas"

if command -v update-desktop-database >/dev/null; then
  update-desktop-database "${DESKTOP_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null; then
  gtk-update-icon-cache -f -t "${ICON_DIR}" >/dev/null 2>&1 || true
fi
if command -v gnome-extensions >/dev/null; then
  gnome-extensions enable "${UUID}" >/dev/null 2>&1 || true
fi
python3 - <<PY
from gi.repository import Gio
uuid = "${UUID}"
settings = Gio.Settings.new("org.gnome.shell")
exts = list(settings.get_strv("enabled-extensions"))
if uuid not in exts:
    exts.append(uuid)
    settings.set_strv("enabled-extensions", exts)
    print(f"Enabled {uuid} for the next GNOME session")
else:
    print(f"{uuid} is already in enabled-extensions")
PY

echo
echo "Installed Google Messages for GNOME"
echo "  Extension: ${EXT_DIR}"
echo "  Helper   : ${BIN_DIR}/messages-gnome"
echo
echo "GNOME Shell 51 loads a new extension UUID only after you log out and back in."
echo "After login, left-click the chat icon in the top bar to show or hide Messages."
echo "Sign in as juanton@wahcha.com and confirm this computer on your phone."
