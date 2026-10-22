package main

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// installDesktopEntry adds TwinStore, with its icon, to the Linux application menu the first
// time it runs (and again when the launcher moves), so later starts are one click from the menu
// or the dock.
func installDesktopEntry(home string, logs *logger) {
	exe, err := os.Executable()
	if err != nil || strings.Contains(exe, "go-build") {
		return
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	icon := filepath.Join(home, "twinstore.png")
	if old, err := os.ReadFile(icon); err != nil || !bytes.Equal(old, iconPNG) {
		_ = os.WriteFile(icon, iconPNG, 0o644)
	}
	apps := os.Getenv("XDG_DATA_HOME")
	if apps == "" {
		user, err := os.UserHomeDir()
		if err != nil {
			return
		}
		apps = filepath.Join(user, ".local", "share")
	}
	apps = filepath.Join(apps, "applications")
	entry := fmt.Sprintf(`[Desktop Entry]
Type=Application
Name=TwinStore
GenericName=Store layout lab
Comment=Store layout simulator with synthetic shoppers
Exec=%s
Icon=%s
Terminal=false
Categories=Science;Office;
StartupNotify=false
`, desktopExec(exe), desktopString(icon))
	path := filepath.Join(apps, "twinstore.desktop")
	if old, err := os.ReadFile(path); err == nil && string(old) == entry {
		return
	}
	if os.MkdirAll(apps, 0o755) != nil || os.WriteFile(path, []byte(entry), 0o755) != nil {
		return
	}
	logs.Printf("Added TwinStore to the application menu (%s)", path)
}

// desktopExec quotes a program path for Exec= as the Desktop Entry specification asks: in double quotes, with ",
// `, $ and \ escaped by a backslash and % doubled; then the value's own escaping doubles every backslash.
func desktopExec(path string) string {
	var quoted strings.Builder
	for _, r := range path {
		switch r {
		case '"', '`', '$', '\\':
			quoted.WriteByte('\\')
		case '%':
			quoted.WriteByte('%')
		}
		quoted.WriteRune(r)
	}
	return desktopString(`"` + quoted.String() + `"`)
}

// desktopString escapes a value of type string: backslashes, and the line breaks and tabs a path could hold.
func desktopString(s string) string {
	return strings.NewReplacer(`\`, `\\`, "\n", `\n`, "\t", `\t`, "\r", `\r`).Replace(s)
}
