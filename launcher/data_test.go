package main

import (
	"encoding/json"
	"errors"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"slices"
	"strings"
	"testing"
	"time"
)

// dataApp is a launcher for app files in "TwinStore 0.4.3/app" with its per-user folder in "home".
func dataApp(t *testing.T) *app {
	t.Helper()
	t.Setenv("PARASTORE_DATA_HOME", "")
	dir := t.TempDir()
	home, root := filepath.Join(dir, "home"), filepath.Join(dir, "TwinStore 0.4.3", "app")
	for _, d := range []string{home, filepath.Join(root, "backend")} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	logs := newLog(filepath.Join(home, "logs"), false)
	t.Cleanup(logs.Close)
	return newApp(home, root, options{}, logs)
}

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

// age sets the modification time of dir and everything in it.
func age(t *testing.T, dir string, when time.Time) {
	t.Helper()
	err := filepath.WalkDir(dir, func(path string, _ fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		return os.Chtimes(path, when, when)
	})
	if err != nil {
		t.Fatal(err)
	}
}

// envValue is the value a process started with env gets: the last setting of name wins.
func envValue(env []string, name string) (string, bool) {
	for i := len(env) - 1; i >= 0; i-- {
		if k, v, _ := strings.Cut(env[i], "="); k == name {
			return v, true
		}
	}
	return "", false
}

func TestEarlierLaunchersLogsNameTheirDataFolders(t *testing.T) {
	for _, c := range []struct{ line, want string }{
		{`09:12:01 » Starting: uv run --project C:\Users\홍길동\OneDrive - 회사\바탕 화면\TwinStore 0.4.1\app\backend --frozen ` +
			`--no-dev --python 3.13 python -m store_emulator.launcher --no-browser --host 127.0.0.1 --port 50123 --exit-with-stdin`,
			`C:\Users\홍길동\OneDrive - 회사\바탕 화면\TwinStore 0.4.1\app\backend\.data`},
		{`10:00:00 » Starting: uv run --project D:\backend tools\TwinStore\app\backend --frozen --with nodejs-wheel-binaries==24.19.0`,
			`D:\backend tools\TwinStore\app\backend\.data`},
		{"21:40:09 » Starting: uv run --project /home/me/Downloads/TwinStore 0.4.0 (1)/app/backend --frozen python -m x",
			"/home/me/Downloads/TwinStore 0.4.0 (1)/app/backend/.data"},
		{`08:00:00 » Data folder: D:\TwinStore 데이터\.data` + "\r", `D:\TwinStore 데이터\.data`},
		{"08:00:00 » Data folder: /Users/me/Library/Application Support/TwinStore/.data",
			"/Users/me/Library/Application Support/TwinStore/.data"},
		{`09:13:00 » Bringing your stores over from E:\Old TwinStore\app\backend\.data`, `E:\Old TwinStore\app\backend\.data`},
		{`09:13:05 » Brought 2 stores over into C:\Users\me\AppData\Local\TwinStore\.data: 3 files copied (0.1 MB)`, ""},
		{`09:13:05 » Could not bring your stores over from E:\Old TwinStore\app: disk full`, ""},
		{"[TwinStore] Starting on http://127.0.0.1:50123 …", ""},
		{"uv run --project /srv/someone/backend --frozen", ""}, // not a line of the launcher's own
		{"09:12:01 » Using /home/me/.local/share/twinstore/bin/uv", ""},
		{"", ""},
	} {
		if got := dataNamedIn(c.line); got != c.want {
			t.Errorf("dataNamedIn(%q) = %q; want %q", c.line, got, c.want)
		}
	}

	a := dataApp(t)
	logs := filepath.Dir(a.log.path)
	writeFile(t, filepath.Join(logs, "launcher.prev.log"), "10:00:00 » TwinStore launcher 0.4.1\n"+
		"10:00:00 » Starting: uv run --project /old/TwinStore 0.4.1/app/backend --frozen --no-dev\n"+
		strings.Repeat("x", 200*1024)+"\n"+ // a long line of server output
		"10:05:00 » Data folder: /old/home/.data\r\n"+
		"10:06:00 » Starting: uv run --project /old/TwinStore 0.4.1/app/backend --frozen --no-dev")
	a.log.Printf("Starting: uv run --project %s --frozen --no-dev", filepath.Join(a.root, "backend"))
	got := a.earlierData()
	here := filepath.Join(a.root, "backend", ".data")
	want := []string{here, here, "/old/TwinStore 0.4.1/app/backend/.data", "/old/home/.data", "/old/TwinStore 0.4.1/app/backend/.data"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("earlier data folders:\n got %q\nwant %q", got, want)
	}
	// Noted before the logs turned over, they stay in the list once the logs no longer name them.
	rememberEarlierData(a.home)
	for _, name := range []string{"launcher.log", "launcher.prev.log"} {
		if err := os.WriteFile(filepath.Join(logs, name), nil, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	got = a.earlierData()
	want = []string{here, here, "/old/TwinStore 0.4.1/app/backend/.data", "/old/home/.data"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("earlier data folders:\n got %q\nwant %q", got, want)
	}
}

func TestTheNewestDataFolderWithAStoreIsBroughtOver(t *testing.T) {
	dir := t.TempDir()
	now := time.Now()
	older, newer := filepath.Join(dir, "0.4.0", ".data"), filepath.Join(dir, "0.4.1", ".data")
	unused, missing := filepath.Join(dir, "unused", ".data"), filepath.Join(dir, "deleted", ".data")
	writeFile(t, filepath.Join(older, "proj_a", "metadata.json"), "{}")
	writeFile(t, filepath.Join(older, "proj_b", "metadata.json"), "{}")
	writeFile(t, filepath.Join(newer, "proj_c", "metadata.json"), "{}")
	writeFile(t, filepath.Join(unused, "llm_cache", "survey", "x.json"), "{}") // caches and settings are no store
	writeFile(t, filepath.Join(unused, "proj_half", "state.json"), "{}")       // nor a folder without metadata.json
	age(t, older, now.Add(-72*time.Hour))
	age(t, newer, now.Add(-48*time.Hour))
	age(t, unused, now)
	candidates := []string{missing, unused, older, newer, older}
	if got, n, err := newestStores(candidates); got != newer || n != 1 || err != nil {
		t.Errorf("chose %q (%d stores, %v); want the newer folder", got, n, err)
	}
	// A run deep inside a store of the older folder is its latest change.
	writeFile(t, filepath.Join(older, "proj_a", "runs", "run_1", "timeline.json"), "[]")
	age(t, older, now.Add(-72*time.Hour))
	age(t, filepath.Join(older, "proj_a", "runs", "run_1"), now.Add(-time.Hour))
	if got, n, err := newestStores(candidates); got != older || n != 2 || err != nil {
		t.Errorf("after a run in the older folder chose %q (%d stores, %v)", got, n, err)
	}
	if got, _, err := newestStores([]string{missing, unused}); got != "" || err != nil {
		t.Errorf("folders without stores gave %q (%v)", got, err)
	}
}

func TestStoresAreBroughtOverOnceAndStayInTheEarlierFolder(t *testing.T) {
	a := dataApp(t)
	defer func(old int64) { linkFrom = old }(linkFrom)
	linkFrom = 1000
	old := filepath.Join(filepath.Dir(filepath.Dir(a.root)), "TwinStore 0.4.1 다운로드", "app")
	src := filepath.Join(old, "backend", ".data")
	kept := map[string]string{
		"proj_a/metadata.json":                   `{"name": "Corner shop"}`,
		"proj_a/runs/run_1/output/timeline.json": "[]",
		"settings/providers.json":                `{"openai": "sk-test"}`,
		"local_vlm/models/qwen.gguf":             strings.Repeat("w", 2000),
	}
	left := []string{"local_vlm/bin/cpu/llama-server", "local_vlm/models/mmproj.gguf.part", "proj_a/state.json.tmp-1a2b3c"}
	for rel, content := range kept {
		writeFile(t, filepath.Join(src, filepath.FromSlash(rel)), content)
	}
	for _, rel := range left {
		writeFile(t, filepath.Join(src, filepath.FromSlash(rel)), "x")
	}
	if err := os.Chmod(filepath.Join(src, "settings", "providers.json"), 0o600); err != nil {
		t.Fatal(err)
	}
	stamp := time.Date(2026, 10, 1, 9, 30, 0, 0, time.UTC)
	if err := os.Chtimes(filepath.Join(src, "proj_a", "metadata.json"), stamp, stamp); err != nil {
		t.Fatal(err)
	}
	writeFile(t, filepath.Join(filepath.Dir(a.log.path), "launcher.prev.log"),
		"10:00:00 » Starting: uv run --project "+filepath.Join(old, "backend")+" --frozen --no-dev\n")
	writeFile(t, filepath.Join(a.home, ".data.migrating", "half.json"), "{") // a copy cut short

	if err := a.bringStoresOver(); err != nil {
		t.Fatal(err)
	}
	dest := filepath.Join(a.home, ".data")
	for rel, content := range kept {
		for _, base := range []string{src, dest} {
			if got, err := os.ReadFile(filepath.Join(base, filepath.FromSlash(rel))); err != nil || string(got) != content {
				t.Errorf("%s in %s: %q, %v", rel, base, got, err)
			}
		}
	}
	for _, rel := range append(left, "half.json") {
		if _, err := os.Stat(filepath.Join(dest, filepath.FromSlash(rel))); !errors.Is(err, fs.ErrNotExist) {
			t.Errorf("%s was brought over (%v)", rel, err)
		}
	}
	if _, err := os.Stat(dest + ".migrating"); !errors.Is(err, fs.ErrNotExist) {
		t.Errorf("the copy was left in .data.migrating (%v)", err)
	}
	same := func(rel string) bool {
		before, errBefore := os.Stat(filepath.Join(src, filepath.FromSlash(rel)))
		after, errAfter := os.Stat(filepath.Join(dest, filepath.FromSlash(rel)))
		return errBefore == nil && errAfter == nil && os.SameFile(before, after)
	}
	if !same("local_vlm/models/qwen.gguf") {
		t.Error("the model was copied, not linked, on the same volume")
	}
	if same("proj_a/metadata.json") {
		t.Error("a small file is shared by both versions")
	}
	if st, err := os.Stat(filepath.Join(dest, "proj_a", "metadata.json")); err != nil || !st.ModTime().Equal(stamp) {
		t.Errorf("modification time not kept: %v", err)
	}
	if st, err := os.Stat(filepath.Join(dest, "settings", "providers.json")); runtime.GOOS != "windows" && (err != nil || st.Mode().Perm() != 0o600) {
		t.Errorf("the API keys file is no longer private: %v", err)
	}
	stage := func() stage {
		i := slices.IndexFunc(a.status.view().Stages, func(s stage) bool { return s.ID == "data" })
		return a.status.view().Stages[i]
	}
	if s := stage(); s.State != "done" || !strings.Contains(s.Detail, "1 brought over from "+old) {
		t.Errorf("boot screen step: %+v", s)
	}
	if !slices.Contains(a.log.Tail(20), "» Bringing your stores over from "+src) {
		t.Errorf("the source is not in the log: %q", a.log.Tail(20))
	}

	// A second start finds the data folder and brings nothing over again.
	writeFile(t, filepath.Join(src, "proj_b", "metadata.json"), "{}")
	a.status.reset()
	if err := a.bringStoresOver(); err != nil {
		t.Fatal(err)
	}
	if fileExists(filepath.Join(dest, "proj_b", "metadata.json")) {
		t.Error("a second start brought the stores over again")
	}
	if s := stage(); s.State != "done" || s.Detail != "ready" {
		t.Errorf("second start step: %+v", s)
	}
}

func TestALargeFileIsCopiedWhereItCannotBeLinked(t *testing.T) {
	defer func(from int64, link func(string, string) error) { linkFrom, linkFile = from, link }(linkFrom, linkFile)
	linkFrom = 1000
	linkFile = func(string, string) error { return errors.New("invalid cross-device link") }
	dir := t.TempDir()
	src, dest := filepath.Join(dir, "old", ".data"), filepath.Join(dir, "home", ".data")
	model := strings.Repeat("w", 4000)
	writeFile(t, filepath.Join(src, "local_vlm", "models", "qwen.gguf"), model)
	writeFile(t, filepath.Join(src, "proj_a", "metadata.json"), "{}")
	st, err := copyData(src, dest)
	if err != nil {
		t.Fatal(err)
	}
	if st.copied != 2 || st.linked != 0 || st.copiedBytes != 4002 {
		t.Errorf("copy counts: %+v", st)
	}
	got, err := os.ReadFile(filepath.Join(dest, "local_vlm", "models", "qwen.gguf"))
	if err != nil || string(got) != model {
		t.Errorf("model not copied: %d bytes, %v", len(got), err)
	}
}

func TestTheServerKeepsItsDataAndPythonInTheUserFolder(t *testing.T) {
	a := dataApp(t)
	check := func(env []string, name, want string) {
		t.Helper()
		if got, _ := envValue(env, name); got != want {
			t.Errorf("%s = %q; want %q", name, got, want)
		}
	}
	env := a.backendEnv("uv 0.11.2")
	check(env, "PARASTORE_DATA_HOME", a.home)
	check(env, "UV_PROJECT_ENVIRONMENT", filepath.Join(a.home, "venv"))
	if _, set := envValue(env, "PYTHONDONTWRITEBYTECODE"); set {
		t.Error("app files that can be written lost their compiled sources")
	}
	resp := httptest.NewRecorder()
	a.handler().ServeHTTP(resp, httptest.NewRequest(http.MethodGet, "http://127.0.0.1/__twinstore/status", nil))
	var view statusView
	if err := json.Unmarshal(resp.Body.Bytes(), &view); err != nil || view.Data != filepath.Join(a.home, ".data") {
		t.Errorf("boot screen data folder = %q (%v)", view.Data, err)
	}

	// A data folder the user chose wins (a relative one from the app folder, as the server reads it), gets a Python
	// environment of its own in the per-user folder (a launcher on it may run beside one on the per-user data, and
	// the lock is per data folder), and is not filled from earlier versions.
	mine := filepath.Join(t.TempDir(), "stores")
	t.Setenv("PARASTORE_DATA_HOME", mine)
	env = a.backendEnv("uv 0.11.2")
	check(env, "PARASTORE_DATA_HOME", mine)
	own, _ := envValue(env, "UV_PROJECT_ENVIRONMENT")
	if filepath.Dir(own) != a.home || !strings.HasPrefix(filepath.Base(own), "venv-") {
		t.Errorf("the chosen data folder's environment is %q; want a venv-<hash> of its own in %s", own, a.home)
	}
	t.Setenv("PARASTORE_DATA_HOME", filepath.Join(t.TempDir(), "other stores"))
	if again, _ := envValue(a.backendEnv("uv 0.11.2"), "UV_PROJECT_ENVIRONMENT"); again == own {
		t.Errorf("two chosen data folders share the environment %q", own)
	}
	t.Setenv("PARASTORE_DATA_HOME", mine)
	if again, _ := envValue(a.backendEnv("uv 0.11.2"), "UV_PROJECT_ENVIRONMENT"); again != own {
		t.Errorf("the environment of a data folder moved from %q to %q", own, again)
	}
	t.Setenv("PARASTORE_DATA_HOME", "my stores")
	check(a.backendEnv("uv 0.11.2"), "PARASTORE_DATA_HOME", filepath.Join(a.root, "my stores"))
	writeFile(t, filepath.Join(a.root, "backend", ".data", "proj_a", "metadata.json"), "{}")
	if err := a.bringStoresOver(); err != nil || fileExists(filepath.Join(a.root, "my stores", ".data", "proj_a", "metadata.json")) {
		t.Errorf("the chosen data folder was filled from an earlier version (%v)", err)
	}

	// The macOS bundle: read-only app files, data in the per-user folder as before.
	t.Setenv("PARASTORE_DATA_HOME", "")
	bundle := newApp(a.home, "/Applications/TwinStore.app/Contents/Resources/app", options{}, a.log)
	env = bundle.backendEnv("uv 0.11.2")
	check(env, "PARASTORE_DATA_HOME", a.home)
	check(env, "PYTHONDONTWRITEBYTECODE", "1")

	// 0.4.2 kept environments for long Windows app folder paths in venv\<hash>: the environment goes beside them.
	writeFile(t, filepath.Join(a.home, "venv", "1a2b3c4d", "pyvenv.cfg"), "")
	check(a.backendEnv("uv 0.11.2"), "UV_PROJECT_ENVIRONMENT", filepath.Join(a.home, "venv", "app"))
	// An environment already there stays in use, also once 0.4.2 adds one inside it for a long app folder path.
	other := t.TempDir()
	writeFile(t, filepath.Join(other, "venv", "pyvenv.cfg"), "")
	writeFile(t, filepath.Join(other, "venv", "1a2b3c4d", "pyvenv.cfg"), "")
	if got := pythonEnv(other, other); got != filepath.Join(other, "venv") {
		t.Errorf("an existing environment was passed over for %q", got)
	}
}

func TestAFirstStartBringsTheStoresOverBeforeTheServerStarts(t *testing.T) {
	t.Setenv("PARASTORE_DATA_HOME", "")
	a, dir := testLauncher(t)
	writeFile(t, filepath.Join(a.root, "backend", ".data", "proj_a", "metadata.json"), "{}") // unpacked over the old version
	leftover := filepath.Join(a.home, "venv", "1a2b3c4d", "pyvenv.cfg")                      // 0.4.2, a long app folder path
	writeFile(t, leftover, "")
	if err := os.WriteFile(filepath.Join(dir, "release"), nil, 0o600); err != nil {
		t.Fatal(err)
	}
	a.start()
	var given []byte
	waitForLauncher(t, func() bool {
		if runs, _ := filepath.Glob(filepath.Join(dir, "run-*")); len(runs) == 1 {
			given, _ = os.ReadFile(runs[0])
		}
		return len(given) > 0
	})
	// uv refuses a folder that holds files but is no environment ("cannot be used because it is not a valid Python
	// environment"), so beside 0.4.2's environments, which another app folder may still use, it gets its own.
	if want := a.home + "\n" + filepath.Join(a.home, "venv", "app"); string(given) != want {
		t.Errorf("the server was given %q; want %q", given, want)
	}
	if !fileExists(leftover) {
		t.Error("0.4.2's environment was removed")
	}
	if !fileExists(filepath.Join(a.home, ".data", "proj_a", "metadata.json")) || a.status.state("data") != "done" {
		t.Errorf("the stores were not brought over before the server started (step %s)", a.status.state("data"))
	}
}
