#!/usr/bin/env bash
# Builds the TwinStore launcher for every OS into launcher/dist — from any OS, no C compiler:
#
#   TwinStore.exe            Windows x64 (icon and version info embedded, no console window)
#   TwinStore.app            macOS universal (Apple silicon + Intel), app files go in Contents/Resources/app
#   twinstore-linux-x64      Linux x64 (adds itself to the application menu on first start)
#   twinstore-linux-arm64    Linux arm64
#
# Needs Go ≥ 1.23 and Python 3. go-winres (Windows resources) is installed on first use.
# VERSION=1.2.3 launcher/build.sh stamps the version.
set -euo pipefail
cd "$(dirname "$0")"
VERSION="${VERSION:-0.0.0-dev}"
NUMERIC="$(printf '%s' "$VERSION" | sed -E 's/^v//; s/^([0-9]+(\.[0-9]+){0,3}).*/\1/')"
[[ "$NUMERIC" =~ ^[0-9]+(\.[0-9]+)*$ ]] || NUMERIC="0.0.0"
LDFLAGS="-s -w -X main.version=$VERSION"
export CGO_ENABLED=0
rm -rf dist && mkdir -p dist

GOWINRES="$(go env GOPATH)/bin/go-winres"
[ -x "$GOWINRES" ] || go install github.com/tc-hib/go-winres@v0.3.3
"$GOWINRES" make --in winres/winres.json --arch amd64 --product-version "$NUMERIC" --file-version "$NUMERIC"
GOOS=windows GOARCH=amd64 go build -trimpath -ldflags "$LDFLAGS -H windowsgui" -o dist/TwinStore.exe .
rm -f rsrc_windows_*.syso

GOOS=darwin GOARCH=amd64 go build -trimpath -ldflags "$LDFLAGS" -o dist/.mac-amd64 .
GOOS=darwin GOARCH=arm64 go build -trimpath -ldflags "$LDFLAGS" -o dist/.mac-arm64 .
APP=dist/TwinStore.app/Contents
mkdir -p "$APP/MacOS" "$APP/Resources"
python3 tools/lipo.py "$APP/MacOS/twinstore" dist/.mac-amd64 dist/.mac-arm64
chmod +x "$APP/MacOS/twinstore"
rm dist/.mac-amd64 dist/.mac-arm64
sed "s/@VERSION@/$NUMERIC/g" macos/Info.plist > "$APP/Info.plist"
printf 'APPL????' > "$APP/PkgInfo"
cp icon/TwinStore.icns "$APP/Resources/TwinStore.icns"

GOOS=linux GOARCH=amd64 go build -trimpath -ldflags "$LDFLAGS" -o dist/twinstore-linux-x64 .
GOOS=linux GOARCH=arm64 go build -trimpath -ldflags "$LDFLAGS" -o dist/twinstore-linux-arm64 .

echo "Built TwinStore launcher $VERSION:"
ls -1 dist
