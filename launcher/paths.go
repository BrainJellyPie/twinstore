package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"hash/crc32"
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
	if json.Unmarshal(raw, &inst) != nil || !sameRoot(runtime.GOOS, inst.Root, root) || inst.URL == "" {
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
	if json.NewDecoder(resp.Body).Decode(&ping) != nil || ping.App != "twinstore-launcher" || !sameRoot(runtime.GOOS, ping.Root, root) {
		return "", false
	}
	return inst.URL, true
}

// sameRoot compares two app folders as the file system does: Windows ignores case.
func sameRoot(goos, a, b string) bool {
	return a == b || goos == "windows" && strings.EqualFold(a, b)
}

// claimInstance makes this launcher the one for these app files, or returns the address of the launcher that is.
// A lock taken before the running-instance check, held until this launcher ends, keeps a second click from starting
// a second server on the same data while the first launcher has not noted its address yet. A launcher holding the
// lock is awaited until it answers, up to wait; after that neither unlock nor an address comes back.
func claimInstance(home, root string, wait time.Duration) (unlock func(), url string) {
	key := root
	if runtime.GOOS == "windows" {
		key = strings.ToLower(key)
	}
	lock := filepath.Join(home, fmt.Sprintf("running-%08x.lock", crc32.ChecksumIEEE([]byte(key))))
	deadline := time.Now().Add(wait)
	for {
		unlock, busy := tryLock(lock)
		if url, ok := runningInstance(home, root); ok { // also one from a launcher older than the lock
			unlock()
			return nil, url
		}
		if !busy {
			return unlock, ""
		}
		if time.Now().After(deadline) {
			return nil, ""
		}
		time.Sleep(250 * time.Millisecond)
	}
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
