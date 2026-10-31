#!/usr/bin/env bash
set -euo pipefail

UUID="google-messages@juanton.local"
APP_ID="org.juanton.MessagesGnome"
BIN_DIR="${HOME}/.local/bin"
DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"

pkill -f "${DATA_HOME}/messages-gnome/messages-gnome" 2>/dev/null || true
pkill -f "${BIN_DIR}/messages-gnome" 2>/dev/null || true

if command -v gnome-extensions >/dev/null; then
  gnome-extensions disable "${UUID}" >/dev/null 2>&1 || true
fi

/bin/rm -f "${BIN_DIR}/messages-gnome" "${HOME}/bin/messages-gnome"
/bin/rm -rf "${DATA_HOME}/messages-gnome"
/bin/rm -rf "${DATA_HOME}/gnome-shell/extensions/${UUID}"
/bin/rm -f "${DATA_HOME}/applications/${APP_ID}.desktop"
/bin/rm -f "${DATA_HOME}/dbus-1/services/${APP_ID}.service"
/bin/rm -f "${DATA_HOME}/icons/hicolor/scalable/apps/${APP_ID}.svg"
/bin/rm -f "${DATA_HOME}/icons/hicolor/symbolic/apps/${APP_ID}-symbolic.svg"
/bin/rm -f "${CONFIG_HOME}/autostart/${APP_ID}.desktop"

if [[ "${1:-}" == "--purge" ]]; then
  /bin/rm -rf "${CONFIG_HOME}/messages-gnome"
  /bin/rm -rf "${CACHE_HOME}/messages-gnome"
  echo "Removed saved session, settings, and cache."
fi

if command -v update-desktop-database >/dev/null; then
  update-desktop-database "${DATA_HOME}/applications" >/dev/null 2>&1 || true
fi

echo "Google Messages for GNOME has been uninstalled."
echo "Run uninstall.sh --purge to also delete login cookies and cache."
