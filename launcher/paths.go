package main

import (
	"encoding/json"
	"errors"
	"fmt"
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
	// From its ping, not the note:
	Version  string `json:"-"`
	Stopping bool   `json:"-"` // Quit was asked for; it lets go of the data home within quitWait
}

// One launcher at a time uses a data home: every version shares the stores, which two servers would change under
// each other. That launcher holds running.lock there until it ends, however it ends, and notes its address in
// launcher.json beside it. Launchers before the lock noted theirs in <home>/running.json.
func dataLock(data string) string     { return filepath.Join(data, "running.lock") }
func instancePath(data string) string { return filepath.Join(data, "launcher.json") }
func olderNote(home string) string    { return filepath.Join(home, "running.json") }

// noted returns the launcher a note names while it answers there, with the app folder it answers with.
func noted(path string) (instance, bool) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return instance{}, false
	}
	var inst instance
	if json.Unmarshal(raw, &inst) != nil || inst.URL == "" {
		return instance{}, false
	}
	ping, err := pingLauncher(inst.URL)
	inst.Root, inst.Version, inst.Stopping = ping.Root, ping.Version, ping.Stopping
	return inst, err == nil
}

type ping struct {
	App      string `json:"app"`
	Root     string `json:"root"`
	Version  string `json:"version"`
	Stopping bool   `json:"stopping"`
}

func pingLauncher(url string) (ping, error) {
	client := http.Client{Timeout: 1500 * time.Millisecond}
	resp, err := client.Get(url + "/__twinstore/ping")
	if err != nil {
		return ping{}, err
	}
	defer resp.Body.Close()
	var p ping
	if err := json.NewDecoder(resp.Body).Decode(&p); err != nil || p.App != "twinstore-launcher" {
		return ping{}, fmt.Errorf("no TwinStore launcher at %s", url)
	}
	return p, nil
}

// sameRoot compares two app folders as the file system does: Windows ignores case.
func sameRoot(goos, a, b string) bool {
	return a == b || goos == "windows" && strings.EqualFold(a, b)
}

// sameApp reports whether the launcher found runs these app files. macOS runs a downloaded app that Finder has not
// moved from a random read-only copy (App Translocation), which may be another one at each start: two such copies of
// the same version count as the same app, so a second click shows the running one instead of quitting it.
func sameApp(goos string, holder instance, root, ver string) bool {
	const translocated = "/AppTranslocation/"
	return sameRoot(goos, holder.Root, root) || goos == "darwin" && holder.Version == ver &&
		strings.Contains(holder.Root, translocated) && strings.Contains(root, translocated)
}

// claim is what claimData found. All empty: a launcher holds the data home but has not answered.
type claim struct {
	unlock  func() // this launcher uses the data home until it calls unlock
	url     string // the launcher of these app files that uses it: shown instead
	stopped string // the app folder of another version that quit for this one
	other   string // the app folder of another version that uses it and did not quit
}

var (
	// quitWait is how long another version has to quit: its server takes up to ten seconds to stop.
	quitWait = 30 * time.Second
	// claimWait is how long a launcher that holds the data home but has not noted its address is awaited.
	claimWait = 20 * time.Second
)

// claimData makes this launcher the one that uses the data home. A launcher holding it is awaited until it answers,
// up to wait (it may have only just started), and one that is quitting until it has let go. One for these app files
// is shown instead, as a second click should; one for other app files, another version, is asked to quit, as this one
// has to use the stores now.
func claimData(home, data, root string, wait time.Duration) claim {
	lock := dataLock(data)
	_ = os.MkdirAll(data, 0o755) // a data home the user chose may not exist yet
	var holder instance
	for start := time.Now(); ; {
		unlock, busy := tryLock(lock)
		if !busy {
			return olderLauncher(home, data, root, unlock)
		}
		var answers bool
		if holder, answers = noted(instancePath(data)); answers && !holder.Stopping {
			break
		}
		limit := wait
		if answers { // quitting (Quit, then a click on the icon at once): it lets go in a moment
			limit += quitWait
		}
		if time.Since(start) > limit {
			return claim{}
		}
		time.Sleep(250 * time.Millisecond)
	}
	if sameApp(runtime.GOOS, holder, root, version) {
		return claim{url: holder.URL}
	}
	// While it quits, another launcher may take the data home first: a second click on this version's icon. The
	// stores are then that one's, and waiting longer for them would only end in "still running".
	var unlock func()
	took := false
	if askToQuit(holder.URL, func() bool {
		var busy bool
		if unlock, busy = tryLock(lock); !busy {
			return true
		}
		now, answers := noted(instancePath(data))
		another := now.PID != holder.PID || now.URL != holder.URL || !sameRoot(runtime.GOOS, now.Root, holder.Root)
		if answers && !now.Stopping && another {
			holder, took = now, true
			return true
		}
		return false
	}) && !took {
		return claim{unlock: unlock, stopped: holder.Root}
	}
	if took && sameApp(runtime.GOOS, holder, root, version) {
		return claim{url: holder.URL}
	}
	return claim{other: holder.Root}
}

// smokeClaim takes the data home for --smoke when no launcher holds it, without waiting or asking anyone to quit.
func smokeClaim(data string) claim {
	_ = os.MkdirAll(data, 0o755)
	if unlock, busy := tryLock(dataLock(data)); !busy {
		return claim{unlock: unlock}
	}
	return claim{}
}

// olderLauncher checks for a launcher from before the lock, once this one holds it. One for these app files is
// shown, as before. One in a macOS app bundle elsewhere kept its data in this per-user folder too and is asked to
// quit; on Windows and Linux they kept theirs in their app folder and may go on running.
func olderLauncher(home, data, root string, unlock func()) claim {
	inst, answers := noted(olderNote(home))
	switch {
	case !answers:
		return claim{unlock: unlock}
	case sameRoot(runtime.GOOS, inst.Root, root):
		unlock()
		return claim{url: inst.URL}
	case !inBundle(inst.Root) || data != home:
		return claim{unlock: unlock}
	}
	if askToQuit(inst.URL, func() bool { _, err := pingLauncher(inst.URL); return err != nil }) {
		return claim{unlock: unlock, stopped: inst.Root}
	}
	unlock()
	return claim{other: inst.Root}
}

// askToQuit asks the launcher at url to quit, as its Quit button does, and waits up to quitWait until gone says it
// has: it stops its server first, then lets go of the data home.
func askToQuit(url string, gone func() bool) bool {
	if req, err := http.NewRequest(http.MethodPost, url+"/__twinstore/quit", nil); err == nil {
		req.Header.Set("X-TwinStore", "1")
		client := http.Client{Timeout: 3 * time.Second}
		if resp, err := client.Do(req); err == nil {
			resp.Body.Close()
		}
	}
	for deadline := time.Now().Add(quitWait); ; {
		if gone() {
			return true
		}
		if time.Now().After(deadline) {
			return false
		}
		time.Sleep(250 * time.Millisecond)
	}
}

func saveInstance(data, root, url string) {
	raw, _ := json.Marshal(instance{URL: url, Root: root, PID: os.Getpid()})
	_ = os.WriteFile(instancePath(data), raw, 0o644)
}

func clearInstance(data, url string) {
	raw, err := os.ReadFile(instancePath(data))
	if err != nil {
		return
	}
	var inst instance
	if json.Unmarshal(raw, &inst) == nil && inst.URL == url && inst.PID == os.Getpid() {
		os.Remove(instancePath(data))
	}
}
