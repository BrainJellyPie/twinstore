package main

import (
	"encoding/json"
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// appHome is the per-user folder for the launcher's own files: uv, logs, the running-instance
// note and — when the app files are read-only, as inside a macOS app bundle — the data and the
// Python environment. Windows %LOCALAPPDATA%\TwinStore, macOS ~/Library/Application Support/TwinStore,
// Linux $XDG_DATA_HOME/twinstore (~/.local/share/twinstore).
func appHome() (string, error) {
	var dir string
	switch runtime.GOOS {
	case "windows":
		dir = os.Getenv("LOCALAPPDATA")
		if dir == "" {
			cfg, err := os.UserConfigDir()
			if err != nil {
				return "", err
			}
			dir = cfg
		}
		dir = filepath.Join(dir, "TwinStore")
	case "darwin":
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		dir = filepath.Join(home, "Library", "Application Support", "TwinStore")
	default:
		dir = os.Getenv("XDG_DATA_HOME")
		if dir == "" {
			home, err := os.UserHomeDir()
			if err != nil {
				return "", err
			}
			dir = filepath.Join(home, ".local", "share")
		}
		dir = filepath.Join(dir, "twinstore")
	}
	return dir, os.MkdirAll(dir, 0o755)
}

// findRoot locates the app files (the folder holding backend/pyproject.toml): inside the macOS
// bundle (Contents/Resources/app), next to the launcher, in an app/ folder beside it, or up to
// three folders above it (a launcher built into launcher/dist of a checkout).
func findRoot() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	dir := filepath.Dir(exe)
	candidates := []string{filepath.Join(dir, "..", "Resources", "app")}
	for d, i := dir, 0; i < 4; d, i = filepath.Dir(d), i+1 {
		candidates = append(candidates, d, filepath.Join(d, "app"))
	}
	if cwd, err := os.Getwd(); err == nil {
		candidates = append(candidates, cwd)
	}
	for _, c := range candidates {
		if fileExists(filepath.Join(c, "backend", "pyproject.toml")) {
			return filepath.Clean(c), nil
		}
	}
	return "", errors.New("the app files were not found next to the launcher — keep TwinStore together with its app folder")
}

// inBundle reports whether the app files live inside a macOS app bundle, where they may be
// read-only (Gatekeeper runs downloaded apps from a read-only copy).
func inBundle(root string) bool {
	return strings.Contains(filepath.ToSlash(root), ".app/Contents/Resources/")
}

func writable(dir string) bool {
	f, err := os.CreateTemp(dir, ".twinstore-write-test-*")
	if err != nil {
		return false
	}
	name := f.Name()
	f.Close()
	os.Remove(name)
	return true
}

func fileExists(path string) bool {
	st, err := os.Stat(path)
	return err == nil && !st.IsDir()
}

func isLinux() bool { return runtime.GOOS == "linux" }

func exeName(name string) string {
	if runtime.GOOS == "windows" {
		return name + ".exe"
	}
	return name
}

type instance struct {
	URL  string `json:"url"`
	Root string `json:"root"`
	PID  int    `json:"pid"`
}

func instancePath(home string) string { return filepath.Join(home, "running.json") }

// runningInstance returns the address of a launcher already serving these app files.
func runningInstance(home, root string) (string, bool) {
	raw, err := os.ReadFile(instancePath(home))
	if err != nil {
		return "", false
	}
	var inst instance
	if json.Unmarshal(raw, &inst) != nil || inst.Root != root || inst.URL == "" {
		return "", false
	}
	client := http.Client{Timeout: 1500 * time.Millisecond}
	resp, err := client.Get(inst.URL + "/__twinstore/ping")
	if err != nil {
		return "", false
	}
	defer resp.Body.Close()
	var ping struct {
		App  string `json:"app"`
		Root string `json:"root"`
	}
	if json.NewDecoder(resp.Body).Decode(&ping) != nil || ping.App != "twinstore-launcher" || ping.Root != root {
		return "", false
	}
	return inst.URL, true
}

func saveInstance(home, root, url string) {
	raw, _ := json.Marshal(instance{URL: url, Root: root, PID: os.Getpid()})
	_ = os.WriteFile(instancePath(home), raw, 0o644)
}

func clearInstance(home, url string) {
	raw, err := os.ReadFile(instancePath(home))
	if err != nil {
		return
	}
	var inst instance
	if json.Unmarshal(raw, &inst) == nil && inst.URL == url && inst.PID == os.Getpid() {
		os.Remove(instancePath(home))
	}
}
