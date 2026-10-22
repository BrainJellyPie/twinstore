package main

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"encoding/json"
	"errors"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
	"time"
	"unicode/utf8"
)

// Other web pages must not reach the launcher or, through it, the server: the server answers any origin (its
// development setup), and its answer to a preflight used to let any page send Quit.
func TestOtherWebPagesCannotUseTheLauncher(t *testing.T) {
	var reached atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		reached.Add(1)
		w.Header().Set("Access-Control-Allow-Origin", "*") // as the server's CORS settings answer
		w.Header().Set("Access-Control-Allow-Headers", r.Header.Get("Access-Control-Request-Headers"))
		w.Header().Set("Access-Control-Allow-Methods", "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT")
		writeJSON(w, map[string]bool{"ok": true})
	}))
	defer server.Close()
	dir := t.TempDir()
	logs := newLog(filepath.Join(dir, "logs"), false)
	defer logs.Close()
	a := newApp(dir, dir, options{}, logs)
	target, _ := url.Parse(server.URL)
	a.target.Store(target)
	handler := a.handler()
	send := func(method, path string, headers ...string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(method, "http://127.0.0.1:8000"+path, nil)
		for i := 0; i+1 < len(headers); i += 2 {
			req.Header.Set(headers[i], headers[i+1])
		}
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		return rec
	}
	evil := "https://evil.example"
	for _, c := range []struct {
		method, path string
		headers      []string
	}{
		{http.MethodOptions, "/__twinstore/quit", []string{"Origin", evil, "Access-Control-Request-Method", "POST",
			"Access-Control-Request-Headers", "x-twinstore"}},
		{http.MethodPost, "/__twinstore/quit", []string{"Origin", evil, "X-TwinStore", "1"}},
		{http.MethodPost, "/__twinstore/retry", []string{"Origin", evil, "X-TwinStore", "1"}},
		{http.MethodPost, "/__twinstore/skip-data", []string{"Origin", "null", "X-TwinStore", "1"}},
		{http.MethodPut, "/api/providers/openai", []string{"Origin", evil}},
		{http.MethodGet, "/api/providers", []string{"Origin", evil}},
		{http.MethodPost, "/api/projects/x/delete", []string{"Sec-Fetch-Site", "cross-site", "Sec-Fetch-Mode", "no-cors"}},
		{http.MethodGet, "/api/projects", []string{"Sec-Fetch-Site", "cross-site", "Sec-Fetch-Mode", "no-cors"}},
	} {
		if rec := send(c.method, c.path, c.headers...); rec.Code != http.StatusForbidden {
			t.Errorf("%s %s from another page: %d", c.method, c.path, rec.Code)
		}
	}
	select {
	case <-a.quit:
		t.Fatal("another web page quit TwinStore")
	default:
	}
	if reached.Load() != 0 {
		t.Errorf("%d requests from other pages reached the server", reached.Load())
	}

	// The launcher's own paths never go on to the server.
	if rec := send(http.MethodOptions, "/__twinstore/quit"); rec.Code != http.StatusNoContent || rec.Header().Get("Access-Control-Allow-Origin") != "" {
		t.Errorf("a preflight for the launcher's own path: %d %v", rec.Code, rec.Header())
	}
	if rec := send(http.MethodGet, "/__twinstore/quit"); rec.Code != http.StatusNotFound || reached.Load() != 0 {
		t.Errorf("GET /__twinstore/quit: %d, %d requests reached the server", rec.Code, reached.Load())
	}
	// Its own pages, a link from elsewhere and programs work; no CORS answer is passed on.
	for _, headers := range [][]string{
		{"Origin", "http://127.0.0.1:8000", "Sec-Fetch-Site", "same-origin", "Sec-Fetch-Mode", "cors"},
		{"Sec-Fetch-Site", "cross-site", "Sec-Fetch-Mode", "navigate"},
		nil,
	} {
		rec := send(http.MethodGet, "/api/projects", headers...)
		if rec.Code != http.StatusOK {
			t.Errorf("GET with %q: %d", headers, rec.Code)
		}
		for name := range rec.Header() {
			if strings.HasPrefix(name, "Access-Control-") {
				t.Errorf("GET with %q passed on %s", headers, name)
			}
		}
	}
	if rec := send(http.MethodPost, "/__twinstore/quit", "Origin", "http://127.0.0.1:8000", "X-TwinStore", "1"); rec.Code != http.StatusOK {
		t.Fatalf("Quit from the app: %d", rec.Code)
	}
	select {
	case <-a.quit:
	case <-time.After(2 * time.Second):
		t.Error("Quit from the app's own page did not quit")
	}
	if !a.quitting.Load() {
		t.Error("the ping does not say a quitting launcher is stopping")
	}
}

// The logs that name an earlier version's data folder turn over at every start that holds the stores; the folders
// they name are noted before, so a start that did not bring the stores over does not lose them.
func TestEarlierStoresAreFoundAfterTheLogsTurnOver(t *testing.T) {
	t.Setenv("PARASTORE_DATA_HOME", "")
	dir := t.TempDir()
	home := filepath.Join(dir, "home")
	old, root := filepath.Join(dir, "TwinStore 0.4.1", "app"), filepath.Join(dir, "TwinStore 0.5.0", "app")
	writeFile(t, filepath.Join(old, "backend", ".data", "proj_a", "metadata.json"), `{"name":"mine"}`)
	writeFile(t, filepath.Join(root, "backend", "pyproject.toml"), "")
	logDir := filepath.Join(home, "logs")
	writeFile(t, filepath.Join(logDir, "launcher.log"), "10:00:01 » Starting: uv run --project "+
		filepath.Join(old, "backend")+" --frozen --no-dev\n")

	// A start without its app files (TwinStore.exe run from inside the zip) holds nothing and turns nothing over.
	rememberEarlierData(home)
	other := openLog(logDir, false, false)
	other.Printf("TwinStore launcher 0.5.0")
	other.Close()
	if raw, _ := os.ReadFile(filepath.Join(logDir, "launcher.log")); !strings.Contains(string(raw), "0.4.1") {
		t.Fatal("a launcher that does not hold the stores turned the log over")
	}
	if !strings.HasPrefix(filepath.Base(other.path), "launcher.pid-") {
		t.Errorf("it wrote %s", other.path)
	}
	// Two starts that hold the stores but quit before bringing them over turn the old log out entirely.
	for range 2 {
		rememberEarlierData(home)
		l := openLog(logDir, false, true)
		l.Printf("TwinStore launcher 0.5.0")
		l.Close()
	}
	rememberEarlierData(home)
	logs := openLog(logDir, false, true)
	defer logs.Close()
	a := newApp(home, root, options{}, logs)
	if err := a.bringStoresOver(); err != nil {
		t.Fatal(err)
	}
	if !fileExists(filepath.Join(home, ".data", "proj_a", "metadata.json")) {
		t.Fatalf("the stores of %s were not brought over (%+v)", old, a.status.view().Stages[1])
	}
	if fileExists(earlierDataNote(home)) {
		t.Error("the note of earlier data folders outlived the copy")
	}
}

// A folder that may hold the stores but cannot be read stops the start: the server would otherwise add the sample
// stores, and the stores would never be brought over.
func TestAnUnreadableEarlierFolderIsNotTakenForNoStores(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("folder permissions")
	}
	a := dataApp(t)
	src := filepath.Join(a.root, "backend", ".data")
	writeFile(t, filepath.Join(src, "proj_a", "metadata.json"), "{}")
	if err := os.Chmod(src, 0); err != nil {
		t.Fatal(err)
	}
	defer os.Chmod(src, 0o755)
	if _, err := os.ReadDir(src); err == nil {
		t.Skip("running with rights that read any folder")
	}
	if err := a.bringStoresOver(); err == nil || !strings.Contains(err.Error(), "cannot be read") {
		t.Errorf("an unreadable earlier folder: %v", err)
	}
	if fileExists(filepath.Join(a.home, ".data")) {
		t.Error("the data folder was made")
	}
}

// Files that cannot be read are left out and named in the log; a store's metadata.json cannot be, and then the boot
// screen offers to start without them.
func TestUnreadableFilesAreLeftOutAndReported(t *testing.T) {
	defer func(open func(string) (*os.File, error)) { openSource = open }(openSource)
	var unreadable []string
	openSource = func(name string) (*os.File, error) {
		for _, rel := range unreadable {
			if strings.HasSuffix(filepath.ToSlash(name), rel) {
				return nil, &fs.PathError{Op: "open", Path: name, Err: fs.ErrPermission}
			}
		}
		return os.Open(name)
	}
	dir := t.TempDir()
	src, dest := filepath.Join(dir, "old", ".data"), filepath.Join(dir, "home", ".data")
	writeFile(t, filepath.Join(src, "proj_a", "metadata.json"), "{}")
	writeFile(t, filepath.Join(src, "proj_a", "runs", "r1", "timeline.json"), "[]")
	writeFile(t, filepath.Join(src, "llm_cache", "x.json"), "{}")

	unreadable = []string{"llm_cache/x.json"}
	st, err := copyData(src, dest)
	if err != nil {
		t.Fatalf("an unreadable cache file stopped the copy: %v", err)
	}
	if len(st.unreadable) != 1 || !strings.HasPrefix(st.unreadable[0], "llm_cache/x.json: ") || st.copied != 2 {
		t.Errorf("copy: %+v", st)
	}
	if fileExists(filepath.Join(dest, "llm_cache", "x.json")) || !fileExists(filepath.Join(dest, "proj_a", "runs", "r1", "timeline.json")) {
		t.Error("the copy holds the wrong files")
	}

	unreadable = []string{"proj_a/metadata.json"}
	a, uvDir := testLauncher(t)
	t.Setenv("PARASTORE_DATA_HOME", "")
	writeFile(t, filepath.Join(a.root, "backend", ".data", "proj_a", "metadata.json"), "{}")
	if err := os.WriteFile(filepath.Join(uvDir, "release"), nil, 0o600); err != nil {
		t.Fatal(err)
	}
	a.start()
	view := a.status.view()
	if !strings.Contains(view.Error, "Start without them") || view.Offer != "skip-data" || markerCount(uvDir, "run") != 0 {
		t.Fatalf("boot screen after a failed copy: %+v, %d servers", view, markerCount(uvDir, "run"))
	}
	req := httptest.NewRequest(http.MethodPost, "http://127.0.0.1/__twinstore/skip-data", nil)
	req.Header.Set("X-TwinStore", "1")
	a.handler().ServeHTTP(httptest.NewRecorder(), req)
	waitForLauncher(t, func() bool { return markerCount(uvDir, "run") == 1 })
	i := slices.IndexFunc(a.status.view().Stages, func(s stage) bool { return s.ID == "data" })
	if s := a.status.view().Stages[i]; s.State != "done" || s.Detail != "started without them" {
		t.Errorf("data step after Start without them: %+v", s)
	}
	if !fileExists(filepath.Join(a.root, "backend", ".data", "proj_a", "metadata.json")) {
		t.Error("the earlier stores were touched")
	}
}

// Run as a user without rights to the file: the real permission error, not a stand-in.
func TestAFileWithoutReadPermissionIsLeftOut(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("file permissions")
	}
	dir := t.TempDir()
	src, dest := filepath.Join(dir, "old", ".data"), filepath.Join(dir, "home", ".data")
	writeFile(t, filepath.Join(src, "proj_a", "metadata.json"), "{}")
	writeFile(t, filepath.Join(src, "llm_cache", "x.json"), "{}")
	if err := os.Chmod(filepath.Join(src, "llm_cache", "x.json"), 0); err != nil {
		t.Fatal(err)
	}
	if f, err := os.Open(filepath.Join(src, "llm_cache", "x.json")); err == nil {
		f.Close()
		t.Skip("running with rights that read any file")
	}
	st, err := copyData(src, dest)
	if err != nil || len(st.unreadable) != 1 || !fileExists(filepath.Join(dest, "proj_a", "metadata.json")) {
		t.Errorf("copy: %+v, %v", st, err)
	}
}

type fakeEntry struct {
	name string
	mode fs.FileMode
}

func (e fakeEntry) Name() string               { return e.name }
func (e fakeEntry) IsDir() bool                { return e.mode.IsDir() }
func (e fakeEntry) Type() fs.FileMode          { return e.mode.Type() }
func (e fakeEntry) Info() (fs.FileInfo, error) { return nil, errors.New("not used") }

// Files OneDrive keeps (cloud files) are reparse points, which Go reports as irregular: they are read like any file.
func TestCloudFilesAreNotLeftOut(t *testing.T) {
	for _, c := range []struct {
		entry fakeEntry
		out   bool
	}{
		{fakeEntry{"metadata.json", fs.ModeIrregular}, false},
		{fakeEntry{"metadata.json", 0}, false},
		{fakeEntry{"pipe", fs.ModeNamedPipe}, true},
		{fakeEntry{"socket", fs.ModeSocket}, true},
		{fakeEntry{"model.gguf.part", 0}, true},
		{fakeEntry{"bin", fs.ModeDir}, false},
	} {
		if got := leftOut(filepath.Join("proj_a", c.entry.name), c.entry); got != c.out {
			t.Errorf("leftOut(%s, %v) = %v", c.entry.name, c.entry.mode, got)
		}
	}
	if leftOut(filepath.Join("local_vlm", "bin"), fakeEntry{"bin", fs.ModeDir | fs.ModeIrregular}) {
		t.Error("the llama.cpp runtime is left behind: the model brought over would not start without a download")
	}
}

// A store moved to another disk and linked back is brought over, and counted; a link round to a folder above is
// not followed for ever. Only the model is hard-linked: a store's large files may be rewritten in place.
func TestLinkedStoresAreBroughtOver(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("symbolic links need rights on Windows")
	}
	defer func(old int64) { linkFrom = old }(linkFrom)
	linkFrom = 1000
	dir := t.TempDir()
	src, dest := filepath.Join(dir, "old", ".data"), filepath.Join(dir, "home", ".data")
	elsewhere := filepath.Join(dir, "big disk", "proj_b")
	writeFile(t, filepath.Join(src, "proj_a", "metadata.json"), "{}")
	writeFile(t, filepath.Join(src, "proj_a", "captures", "c1", "overlay.png"), strings.Repeat("p", 2000))
	writeFile(t, filepath.Join(src, "local_vlm", "models", "qwen.gguf"), strings.Repeat("w", 2000))
	writeFile(t, filepath.Join(elsewhere, "metadata.json"), `{"name":"linked"}`)
	writeFile(t, filepath.Join(dir, "settings.json"), "{}")
	for link, to := range map[string]string{
		filepath.Join(src, "proj_b"):                  elsewhere,
		filepath.Join(elsewhere, "loop"):              src,
		filepath.Join(src, "proj_a", "settings.json"): filepath.Join(dir, "settings.json"),
		filepath.Join(src, "proj_a", "gone.json"):     filepath.Join(dir, "nothing"),
	} {
		if err := os.Symlink(to, link); err != nil {
			t.Fatal(err)
		}
	}
	if n, _, err := storesIn(src); n != 2 || err != nil {
		t.Errorf("storesIn counted %d stores (%v)", n, err)
	}
	st, err := copyData(src, dest)
	if err != nil {
		t.Fatal(err)
	}
	for _, rel := range []string{"proj_b/metadata.json", "proj_a/settings.json"} {
		if info, err := os.Lstat(filepath.Join(dest, rel)); err != nil || !info.Mode().IsRegular() {
			t.Errorf("%s: %v", rel, err)
		}
	}
	if fileExists(filepath.Join(dest, "proj_b", "loop", "proj_a", "metadata.json")) {
		t.Error("a link round to the data folder was followed")
	}
	same := func(rel string) bool {
		before, _ := os.Stat(filepath.Join(src, rel))
		after, err := os.Stat(filepath.Join(dest, rel))
		return err == nil && os.SameFile(before, after)
	}
	if !same("local_vlm/models/qwen.gguf") || same("proj_a/captures/c1/overlay.png") {
		t.Errorf("hard links: model %v, overlay %v (%+v)", same("local_vlm/models/qwen.gguf"), same("proj_a/captures/c1/overlay.png"), st)
	}
}

// Quit, then a click on the icon at once: the click waits for the quitting launcher to let go, then starts.
func TestAClickWhileTheAppQuitsWaitsForIt(t *testing.T) {
	defer func(old time.Duration) { quitWait = old }(quitWait)
	quitWait = 5 * time.Second
	home := t.TempDir()
	root := filepath.Join(home, "app files")
	holder := claimData(home, home, root, time.Second)
	if holder.unlock == nil {
		t.Fatal("no lock")
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/__twinstore/quit" {
			t.Error("a quitting launcher was asked to quit")
		}
		writeJSON(w, map[string]any{"app": "twinstore-launcher", "root": root, "stopping": true})
	}))
	defer server.Close()
	saveInstance(home, root, server.URL)
	go func() { time.Sleep(600 * time.Millisecond); holder.unlock() }()
	c := claimData(home, home, root, 200*time.Millisecond)
	if c.unlock == nil || c.url != "" {
		t.Fatalf("a click while the app quits: %+v", c)
	}
	c.unlock()
}

// Two clicks on a new version while an older one runs: the first takes over, the second shows it.
func TestASecondClickWhileAnotherVersionQuitsShowsTheFirst(t *testing.T) {
	defer func(old time.Duration) { quitWait = old }(quitWait)
	quitWait = 10 * time.Second
	home := t.TempDir()
	root, older := filepath.Join(home, "TwinStore 0.5.0", "app"), filepath.Join(home, "TwinStore 0.4.4", "app")
	holder := claimData(home, home, older, time.Second)
	var quitting atomic.Bool
	old := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/__twinstore/quit" && quitting.CompareAndSwap(false, true) {
			go func() {
				time.Sleep(300 * time.Millisecond)
				clearInstance(home, "")
				_ = os.Remove(instancePath(home))
				holder.unlock()
			}()
		}
		writeJSON(w, map[string]any{"app": "twinstore-launcher", "root": older, "stopping": quitting.Load()})
	}))
	defer old.Close()
	saveInstance(home, older, old.URL)
	newer, _ := fakeLauncher(t, root, func() { t.Error("the new version was asked to quit") })

	type result struct {
		c    claim
		took time.Duration
	}
	results := make(chan result, 2)
	start := time.Now()
	click := func() {
		c := claimData(home, home, root, 2*time.Second)
		if c.unlock != nil { // the one that took the stores notes its address, as useClaim does
			saveInstance(home, root, newer.URL)
		}
		results <- result{c, time.Since(start)}
	}
	go click()
	time.Sleep(50 * time.Millisecond)
	go click()
	var took, shown int
	for range 2 {
		r := <-results
		switch {
		case r.c.unlock != nil: // the one that asked, or the other once the older one let go
			took++
			defer r.c.unlock()
		case r.c.url == newer.URL && r.took < 5*time.Second:
			shown++
		default:
			t.Errorf("a click got %+v after %s", r.c, r.took)
		}
	}
	if took != 1 || shown != 1 {
		t.Errorf("%d took the stores over, %d showed the one that did", took, shown)
	}
}

// testHome puts the per-user folder in a temporary one.
func testHome(t *testing.T) string {
	t.Helper()
	base := t.TempDir()
	t.Setenv("XDG_DATA_HOME", base)
	t.Setenv("HOME", base)
	t.Setenv("LOCALAPPDATA", base)
	t.Setenv("PARASTORE_DATA_HOME", "")
	home, err := appHome()
	if err != nil {
		t.Fatal(err)
	}
	return home
}

// runLauncher runs the launcher as a double-click does, from the folder cwd (where it finds the app files), and
// returns its exit code.
func runLauncher(t *testing.T, cwd string, opt options) (code chan int) {
	t.Helper()
	was, _ := os.Getwd()
	if err := os.Chdir(cwd); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chdir(was) })
	code = make(chan int, 1)
	go func() { code <- run(opt) }()
	return code
}

// --smoke without the app files fails at once instead of waiting for ever.
func TestSmokeFailsWithoutTheAppFiles(t *testing.T) {
	testHome(t)
	code := runLauncher(t, t.TempDir(), options{smoke: true, noBrowser: true})
	select {
	case c := <-code:
		if c != 1 {
			t.Errorf("exit code %d", c)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("--smoke without the app files did not end")
	}
}

// A launcher holding the stores that does not answer: the boot screen says so, with Try again, instead of a launcher
// that ends after 20 seconds without a word.
func TestAHolderThatDoesNotAnswerIsShownOnTheBootScreen(t *testing.T) {
	defer func(old time.Duration) { claimWait = old }(claimWait)
	claimWait = 300 * time.Millisecond
	root := t.TempDir()
	writeFile(t, filepath.Join(root, "backend", "pyproject.toml"), "")
	home := testHome(t)
	unlock, busy := tryLock(dataLock(home))
	if busy {
		t.Fatal("lock busy")
	}
	defer unlock()
	code := runLauncher(t, root, options{noBrowser: true})
	var page string
	waitFor := time.Now().Add(10 * time.Second)
	for page == "" && time.Now().Before(waitFor) {
		logs, _ := filepath.Glob(filepath.Join(home, "logs", "launcher*.log"))
		for _, log := range logs {
			raw, _ := os.ReadFile(log)
			if m := regexp.MustCompile(`Boot screen at (http://\S+)`).FindStringSubmatch(string(raw)); m != nil {
				page = m[1]
			}
		}
		select {
		case c := <-code:
			t.Fatalf("the launcher ended (%d) without a boot screen", c)
		case <-time.After(50 * time.Millisecond):
		}
	}
	if page == "" {
		t.Fatal("no boot screen")
	}
	resp, err := http.Get(page + "/__twinstore/status")
	if err != nil {
		t.Fatal(err)
	}
	var view statusView
	err = jsonDecode(resp, &view)
	if err != nil || !strings.Contains(view.Error, "does not answer") || !view.CanRetry {
		t.Errorf("boot screen: %+v (%v)", view, err)
	}
	if fileExists(filepath.Join(home, "logs", "launcher.prev.log")) {
		t.Error("a launcher that does not hold the stores turned the log over")
	}
	req, _ := http.NewRequest(http.MethodPost, page+"/__twinstore/quit", nil)
	req.Header.Set("X-TwinStore", "1")
	if resp, err := http.DefaultClient.Do(req); err == nil {
		resp.Body.Close()
	}
	select {
	case c := <-code:
		if c != 0 {
			t.Errorf("exit code %d after Quit", c)
		}
	case <-time.After(15 * time.Second):
		t.Fatal("Quit did not end the launcher")
	}
}

// Without the app files there is nothing to try again.
func TestTryAgainIsOfferedOnlyWithTheAppFiles(t *testing.T) {
	logs := newLog(filepath.Join(t.TempDir(), "logs"), false)
	defer logs.Close()
	for root, want := range map[string]bool{"": false, t.TempDir(): true} {
		a := newApp(t.TempDir(), root, options{}, logs)
		a.status.fail("files", "not found")
		rec := httptest.NewRecorder()
		a.handler().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "http://127.0.0.1/__twinstore/status", nil))
		var view statusView
		if err := jsonDecode(rec.Result(), &view); err != nil || view.CanRetry != want {
			t.Errorf("root %q: can_retry %v (%v)", root, view.CanRetry, err)
		}
	}
}

// The log the boot screen copies is this launcher's own, whatever another launcher did to its name.
func TestTheLogIsReadFromTheLaunchersOwnFile(t *testing.T) {
	dir := t.TempDir()
	logs := newLog(dir, false)
	defer logs.Close()
	logs.Printf("mine")
	if err := os.Rename(filepath.Join(dir, "launcher.log"), filepath.Join(dir, "launcher.prev.log")); err != nil {
		if runtime.GOOS == "windows" {
			return // Windows does not let another launcher rename it
		}
		t.Fatal(err)
	}
	writeFile(t, filepath.Join(dir, "launcher.log"), "another launcher's\n")
	raw, err := logs.Contents()
	if err != nil || !strings.Contains(string(raw), "» mine") || strings.Contains(string(raw), "another") {
		t.Errorf("log: %q (%v)", raw, err)
	}
}

// Windows cannot replace a uv an earlier TwinStore still runs, but can rename it: the new one goes in beside it.
func TestAUVThatIsRunningIsReplaced(t *testing.T) {
	defer func(old func(string, string) error) { renameFile = old }(renameFile)
	bin := t.TempDir()
	target := filepath.Join(bin, exeName("uv"))
	writeFile(t, target, "old uv")
	running := target
	renameFile = func(from, to string) error {
		if to == running && fileExists(to) { // replacing a running program
			return &os.LinkError{Op: "rename", Old: from, New: to, Err: fs.ErrPermission}
		}
		if from == running {
			running = to
		}
		return os.Rename(from, to)
	}
	if err := writeExecutable(target, strings.NewReader("new uv")); err != nil {
		t.Fatal(err)
	}
	if raw, _ := os.ReadFile(target); string(raw) != "new uv" {
		t.Errorf("uv is %q", raw)
	}
	if parts, _ := filepath.Glob(filepath.Join(bin, "*.part-*")); len(parts) != 0 {
		t.Errorf("left %q", parts)
	}
}

// A slow download that keeps going finishes; one that stops is given up after uvStall.
func TestUVDownloadsEndOnlyWhenTheyStall(t *testing.T) {
	asset, err := uvAsset()
	if err != nil {
		t.Skip(err)
	}
	archive := uvArchive(t, filepath.Ext(asset) == ".zip")
	defer func(releases string, stall time.Duration) { uvReleases, uvStall = releases, stall }(uvReleases, uvStall)
	uvStall = 300 * time.Millisecond
	var stall atomic.Bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		flusher := w.(http.Flusher)
		w.Header().Set("Content-Length", strconv.Itoa(len(archive)))
		for i := 0; i < len(archive); i += len(archive)/8 + 1 {
			_, _ = w.Write(archive[i:min(i+len(archive)/8+1, len(archive))])
			flusher.Flush()
			if stall.Load() && i > 0 {
				time.Sleep(3 * time.Second)
				return
			}
			time.Sleep(100 * time.Millisecond) // the whole download takes three times uvStall
		}
	}))
	defer server.Close()
	uvReleases = server.URL + "/"
	home := t.TempDir()
	uv, err := installUV(home, t.Logf)
	if err != nil || !fileExists(uv) {
		t.Fatalf("a slow download: %v", err)
	}
	stall.Store(true)
	if _, err := installUV(t.TempDir(), t.Logf); err == nil || !strings.Contains(err.Error(), "nothing received") {
		t.Errorf("a stalled download: %v", err)
	}
}

func uvArchive(t *testing.T, asZip bool) []byte {
	t.Helper()
	var buf bytes.Buffer
	if asZip {
		zw := zip.NewWriter(&buf)
		for _, name := range []string{"uv.exe", "uvx.exe"} {
			w, _ := zw.Create("uv-x86_64-pc-windows-msvc/" + name)
			_, _ = w.Write([]byte(strings.Repeat("u", 4000)))
		}
		_ = zw.Close()
		return buf.Bytes()
	}
	gz := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gz)
	for _, name := range []string{"uv", "uvx"} {
		body := strings.Repeat("u", 4000)
		_ = tw.WriteHeader(&tar.Header{Name: "uv-x86_64-unknown-linux-musl/" + name, Mode: 0o755, Size: int64(len(body)), Typeflag: tar.TypeReg})
		_, _ = tw.Write([]byte(body))
	}
	_ = tw.Close()
	_ = gz.Close()
	return buf.Bytes()
}

// A program path with any character comes back whole from the menu entry, as the Desktop Entry specification reads it.
func TestTheMenuEntryQuotesTheProgramPath(t *testing.T) {
	for _, path := range []string{
		"/home/me/TwinStore/twinstore",
		`/home/me/Apps/$HOME "x" ` + "`id`" + ` 100% \ 홍길동 (1)/twinstore`,
	} {
		if got := readDesktopExec(t, desktopExec(path)); got != path {
			t.Errorf("Exec for %q reads back as %q", path, got)
		}
	}
	if got := desktopExec("/home/me/TwinStore/twinstore"); got != `"/home/me/TwinStore/twinstore"` {
		t.Errorf("an ordinary path became %s (the entry would be written again)", got)
	}
}

// readDesktopExec reads an Exec value back: the string escapes first, then the quoting, then %%.
func readDesktopExec(t *testing.T, value string) string {
	t.Helper()
	var s strings.Builder
	for i := 0; i < len(value); i++ {
		if value[i] == '\\' && i+1 < len(value) {
			i++
			switch value[i] {
			case 's':
				s.WriteByte(' ')
			case 'n':
				s.WriteByte('\n')
			case 't':
				s.WriteByte('\t')
			case 'r':
				s.WriteByte('\r')
			default:
				s.WriteByte(value[i])
			}
			continue
		}
		s.WriteByte(value[i])
	}
	quoted := s.String()
	if len(quoted) < 2 || quoted[0] != '"' || quoted[len(quoted)-1] != '"' {
		t.Fatalf("not quoted: %s", quoted)
	}
	var arg strings.Builder
	inner := quoted[1 : len(quoted)-1]
	for i := 0; i < len(inner); i++ {
		switch {
		case inner[i] == '\\' && i+1 < len(inner) && strings.ContainsRune("\"`$\\", rune(inner[i+1])):
			i++
		case inner[i] == '"' || inner[i] == '`' || inner[i] == '$':
			t.Fatalf("unescaped %c in %s", inner[i], quoted)
		case inner[i] == '%':
			if i+1 >= len(inner) || inner[i+1] != '%' {
				t.Fatalf("field code in %s", quoted)
			}
			i++
		}
		arg.WriteByte(inner[i])
	}
	return arg.String()
}

// The step text keeps whole characters when a long line is cut short.
func TestALongLineIsCutBetweenCharacters(t *testing.T) {
	dir := t.TempDir()
	logs := newLog(filepath.Join(dir, "logs"), false)
	defer logs.Close()
	a := newApp(dir, dir, options{}, logs)
	exited := make(chan struct{})
	a.exited = exited
	a.status.activate("python", "Checking")
	a.readOutput(strings.NewReader("Resolved C:\\Users\\"+strings.Repeat("홍길동", 40)+"\n"), exited)
	i := slices.IndexFunc(a.status.view().Stages, func(s stage) bool { return s.ID == "python" })
	if detail := a.status.view().Stages[i].Detail; !utf8.ValidString(detail) || !strings.HasSuffix(detail, "…") {
		t.Errorf("step text %q", detail)
	}
}

// macOS may run each start of a downloaded app from another random read-only copy: the same version there is the
// same app.
func TestTranslocatedCopiesOfTheSameVersionAreTheSameApp(t *testing.T) {
	a := "/private/var/folders/x/T/AppTranslocation/1111/d/TwinStore.app/Contents/Resources/app"
	b := "/private/var/folders/x/T/AppTranslocation/2222/d/TwinStore.app/Contents/Resources/app"
	if !sameApp("darwin", instance{Root: a, Version: "0.5.0"}, b, "0.5.0") {
		t.Error("two translocated copies of 0.5.0")
	}
	if sameApp("darwin", instance{Root: a, Version: "0.4.9"}, b, "0.5.0") {
		t.Error("translocated copies of two versions")
	}
	if sameApp("darwin", instance{Root: "/Applications/TwinStore.app/Contents/Resources/app", Version: "0.5.0"}, b, "0.5.0") {
		t.Error("an installed app and a translocated download")
	}
}

func jsonDecode(resp *http.Response, v any) error {
	defer resp.Body.Close()
	return json.NewDecoder(resp.Body).Decode(v)
}
