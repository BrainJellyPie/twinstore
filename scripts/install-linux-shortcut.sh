#!/usr/bin/env bash
# Adds "TwinStore" to the Linux application menu for a source checkout. (The TwinStore launcher
# from a release does this by itself on first start.)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
cat > "$APPS/twinstore.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TwinStore
Comment=Store digital twin with synthetic shoppers
Exec="$ROOT/launcher/scripts/twinstore-linux.sh"
Path=$ROOT
Icon=$ROOT/launcher/icon/twinstore.png
Terminal=true
Categories=Science;Office;
DESKTOP
chmod +x "$APPS/twinstore.desktop"
echo "TwinStore added to the application menu."
