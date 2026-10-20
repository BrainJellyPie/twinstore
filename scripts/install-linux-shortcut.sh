#!/usr/bin/env bash
# Adds "Parastore" to the Linux application menu (and the desktop, if one exists).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
cat > "$APPS/parastore.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Parastore
Comment=Store layout simulator with synthetic shoppers
Exec="$ROOT/Parastore-Linux.sh"
Path=$ROOT
Icon=$ROOT/frontend/public/parastore-icon.svg
Terminal=true
Categories=Science;Office;
DESKTOP
chmod +x "$APPS/parastore.desktop"
if [ -d "$HOME/Desktop" ]; then
  cp "$APPS/parastore.desktop" "$HOME/Desktop/" && chmod +x "$HOME/Desktop/parastore.desktop"
  command -v gio >/dev/null 2>&1 && gio set "$HOME/Desktop/parastore.desktop" metadata::trusted true 2>/dev/null || true
fi
echo "Parastore added to the application menu."
