package main

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"slices"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"
)

// A copy of this test executable stands in for uv. It never starts Python or downloads anything.
func TestMain(m *testing.M) {
	if dir := os.Getenv("TWINSTORE_TEST_MODEL_DIR"); dir != "" {
		serveModel(dir)
	}
	if dir := os.Getenv("TWINSTORE_TEST_UV_DIR"); dir != "" {
		kind := "run"
		if len(os.Args) > 1 && os.Args[1] == "--version" {
			kind = "version"
		}
		if err := os.WriteFile(filepath.Join(dir, fmt.Sprintf("%s-%d", kind, os.Getpid())), nil, 0o600); err != nil {
			os.Exit(2)
		}
		if kind == "version" {
			deadline := time.Now().Add(10 * time.Second)
			for !fileExists(filepath.Join(dir, "release")) && time.Now().Before(deadline) {
				time.Sleep(5 * time.Millisecond)
			}
			fmt.Println("uv 0.99.0 (launcher test)")
		} else if fileExists(filepath.Join(dir, "fail-run")) {
			if fileExists(filepath.Join(dir, "with-model-server")) {
				startModel(dir)
			}
			os.Exit(3)
		} else {
			done := make(chan struct{})
			go func() {
				_, _ = io.Copy(io.Discard, os.Stdin)
				close(done)
			}()
			select {
			case <-done:
			case <-time.After(5 * time.Second):
			}
		}
		os.Exit(0)
	}
	os.Exit(m.Run())
}

// startModel starts a stand-in for llama-server, as the server does, and returns once it holds its port.
func startModel(dir string) {
	executable, err := os.Executable()
	if err != nil {
		os.Exit(2)
	}
	model := exec.Command(executable)
	model.Env = append(os.Environ(), "TWINSTORE_TEST_MODEL_DIR="+dir)
	if model.Start() != nil {
		os.Exit(2)
	}
	for deadline := time.Now().Add(5 * time.Second); markerCount(dir, "model") == 0 && time.Now().Before(deadline); {
		time.Sleep(5 * time.Millisecond)
	}
}

// serveModel holds a port until it is ended, and notes the port in model-<pid>.
func serveModel(dir string) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		os.Exit(2)
	}
	partial := filepath.Join(dir, "partial")
	if os.WriteFile(partial, []byte(strconv.Itoa(ln.Addr().(*net.TCPAddr).Port)), 0o600) != nil ||
		os.Rename(partial, filepath.Join(dir, fmt.Sprintf("model-%d", os.Getpid()))) != nil {
		os.Exit(2)
	}
	time.Sleep(30 * time.Second)
	os.Exit(0)
}

func testLauncher(t *testing.T) (*app, string) {
	t.Helper()
	dir := t.TempDir()
	bin := filepath.Join(dir, "bin")
	root := filepath.Join(dir, "app files")
	for _, path := range []string{bin, filepath.Join(root, "backend")} {
		if err := os.MkdirAll(path, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	executable, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(executable)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(bin, exeName("uv")), data, 0o755); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", bin)
	t.Setenv("TWINSTORE_TEST_UV_DIR", dir)
	logs := newLog(filepath.Join(dir, "logs"), false)
	a := newApp(dir, root, options{noBrowser: true}, logs)
	t.Cleanup(func() {
		_ = os.WriteFile(filepath.Join(dir, "release"), nil, 0o600)
		a.stopBackend(time.Second)
		// Failed assertions must also clean up extra processes launched by the regression.
		for _, kind := range []string{"run", "model"} {
			files, _ := filepath.Glob(filepath.Join(dir, kind+"-*"))
			for _, file := range files {
				pid, _ := strconv.Atoi(strings.TrimPrefix(filepath.Base(file), kind+"-"))
				if process, err := os.FindProcess(pid); err == nil {
					_ = process.Kill()
				}
			}
		}
		logs.Close()
	})
	return a, dir
}

func waitForLauncher(t *testing.T, ready func() bool) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if ready() {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatal("launcher condition did not become ready")
}

func markerCount(dir, kind string) int {
	files, _ := filepath.Glob(filepath.Join(dir, kind+"-*"))
	return len(files)
}

func TestConcurrentStartsLaunchOneBackend(t *testing.T) {
	a, dir := testLauncher(t)
	var wg sync.WaitGroup
	for range 12 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			a.start()
		}()
	}
	waitForLauncher(t, func() bool { return markerCount(dir, "version") > 0 })
	// Hold the first preparation step open while concurrent retries enter start.
	time.Sleep(100 * time.Millisecond)
	if err := os.WriteFile(filepath.Join(dir, "release"), nil, 0o600); err != nil {
		t.Fatal(err)
	}
	wg.Wait()
	waitForLauncher(t, func() bool { return markerCount(dir, "run") > 0 })
	if count := markerCount(dir, "version"); count != 1 {
		t.Errorf("concurrent starts prepared %d processes; want 1", count)
	}
	if count := markerCount(dir, "run"); count != 1 {
		t.Errorf("concurrent starts launched %d backends; want 1", count)
	}
}

func TestStartWhileRunningKeepsTheExistingBackend(t *testing.T) {
	a, dir := testLauncher(t)
	if err := os.WriteFile(filepath.Join(dir, "release"), nil, 0o600); err != nil {
		t.Fatal(err)
	}
	a.start()
	waitForLauncher(t, func() bool { return markerCount(dir, "run") == 1 })
	for range 4 {
		a.start()
	}
	if count := markerCount(dir, "version"); count != 1 {
		t.Errorf("active backend triggered %d preparations; want 1", count)
	}
}

func TestRetryRequestsCannotRestartPreparation(t *testing.T) {
	a, dir := testLauncher(t)
	started := make(chan struct{})
	go func() {
		a.start()
		close(started)
	}()
	waitForLauncher(t, func() bool { return markerCount(dir, "version") == 1 })
	handler := a.handler()
	for range 12 {
		req := httptest.NewRequest(http.MethodPost, "http://127.0.0.1/__twinstore/retry", nil)
		req.Header.Set("X-TwinStore", "1")
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, req)
		if response.Code != http.StatusOK {
			t.Fatalf("retry status = %d", response.Code)
		}
	}
	time.Sleep(100 * time.Millisecond)
	if a.status.state("files") != "done" {
		t.Error("retry reset preparation already in progress")
	}
	if err := os.WriteFile(filepath.Join(dir, "release"), nil, 0o600); err != nil {
		t.Fatal(err)
	}
	<-started
	waitForLauncher(t, func() bool { return markerCount(dir, "run") > 0 })
	if count := markerCount(dir, "version"); count != 1 {
		t.Errorf("retry requests prepared %d processes; want 1", count)
	}
}

func TestFailedStartAllowsANewAttempt(t *testing.T) {
	a, dir := testLauncher(t)
	for _, file := range []string{"release", "fail-run"} {
		if err := os.WriteFile(filepath.Join(dir, file), nil, 0o600); err != nil {
			t.Fatal(err)
		}
	}
	a.start()
	waitForLauncher(t, func() bool { return !a.running() && a.status.view().Error != "" })
	if err := os.Remove(filepath.Join(dir, "fail-run")); err != nil {
		t.Fatal(err)
	}
	a.start()
	waitForLauncher(t, func() bool { return markerCount(dir, "run") == 2 && a.running() })
	if a.status.view().Error != "" {
		t.Error("retry retained the previous startup error")
	}
}

func TestRetryRestartsAServerThatNeverAnswered(t *testing.T) {
	a, dir := testLauncher(t)
	if err := os.WriteFile(filepath.Join(dir, "release"), nil, 0o600); err != nil {
		t.Fatal(err)
	}
	a.start()
	waitForLauncher(t, func() bool { return markerCount(dir, "run") == 1 && a.running() })
	a.retry()
	if count := markerCount(dir, "run"); count != 1 {
		t.Fatalf("retry restarted a healthy start (%d backends)", count)
	}
	a.status.fail("server", "The server has not answered for 15 minutes.")
	a.retry()
	waitForLauncher(t, func() bool { return markerCount(dir, "run") == 2 && a.running() })
	if a.status.view().Error != "" {
		t.Error("restart kept the earlier error")
	}
}

func TestLongWindowsAppFoldersGetAShortPythonEnvironment(t *testing.T) {
	short := `C:\Users\me\Downloads\TwinStore\app`
	long := `C:\Users\someone.name\OneDrive - Company\Desktop\TwinStore-0.4.2-windows-x64\TwinStore\app`
	home := `C:\Users\me\AppData\Local\TwinStore`
	if got := shortVenvFor("windows", short, home); got != "" {
		t.Errorf("short folder moved its environment to %q", got)
	}
	got := shortVenvFor("windows", long, home)
	if !strings.HasPrefix(got, filepath.Join(home, "venv")) || len(got) > len(home)+15 {
		t.Errorf("long folder environment = %q", got)
	}
	if again := shortVenvFor("windows", strings.ToUpper(long), home); again != got {
		t.Errorf("the same folder in other case got another environment: %q", again)
	}
	if other := shortVenvFor("windows", long+"2", home); other == got {
		t.Error("two app folders share one environment")
	}
	if got := shortVenvFor("linux", long, home); got != "" {
		t.Errorf("non-Windows folder moved its environment to %q", got)
	}
}

func TestAnOldUVIsPassedOverForANewerOne(t *testing.T) {
	dir := t.TempDir()
	uv := func(name string) string {
		path := filepath.Join(dir, name)
		if err := os.WriteFile(path, nil, 0o755); err != nil {
			t.Fatal(err)
		}
		return path
	}
	managed, onPath, local, missing := uv("managed"), uv("path"), uv("local"), filepath.Join(dir, "missing")
	versions := map[string]string{managed: "uv 0.11.2 (5c6a6c2 2026-03-31)", onPath: "uv 0.4.18", local: "uv 0.12.0"}
	asked := 0
	versionOf := func(path string) string { asked++; return versions[path] }
	if got, version := pickUV([]string{missing, managed, onPath}, versionOf); got != managed || version != versions[managed] || asked != 1 {
		t.Errorf("current managed uv: got %s (%s) after %d version checks", got, version, asked)
	}
	versions[managed] = "uv 0.5.0"
	if got, _ := pickUV([]string{managed, onPath, onPath, local}, versionOf); got != local {
		t.Errorf("old managed and PATH uv: got %s; want the recent one in a standard folder", got)
	}
	versions[local] = "" // does not answer
	if got, version := pickUV([]string{managed, onPath, local}, versionOf); got != managed || version != "uv 0.5.0" {
		t.Errorf("only old uvs: fallback %s (%s); want the first found", got, version)
	}
	if got, _ := pickUV([]string{missing}, versionOf); got != "" {
		t.Errorf("no uv: got %s", got)
	}
	for version, want := range map[string]bool{"uv 0.11.0": true, "uv 0.11.32 (x86_64-unknown-linux-gnu)": true,
		"uv 1.0.0": true, "uv 0.10.9": false, "uv 0.8.0": false, "uv 0.4.18": false, "": false, "uv test": false} {
		if uvAtLeast(version, minUV) != want {
			t.Errorf("uvAtLeast(%q) = %v", version, !want)
		}
	}
}

func TestServerEnvironmentLeavesOutAnotherPython(t *testing.T) {
	environ := []string{"PATH=/bin", `PYTHONHOME=C:\ArcGIS\Python`, `PythonPath=C:\QGIS\python`, "PYTHONSTARTUP=s.py",
		"PYTHONUTF8=0", `=C:=C:\`}
	got := serverEnv("windows", environ, "uv 0.11.2", "PYTHONUTF8=1")
	want := []string{"PATH=/bin", "PYTHONUTF8=0", `=C:=C:\`, "UV_SYSTEM_CERTS=1", "PYTHONUTF8=1"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("Windows environment:\n got %q\nwant %q", got, want)
	}
	got = serverEnv("linux", environ, "uv 0.9.5", "PYTHONUTF8=1")
	if slices.Contains(got, "PYTHONSTARTUP=s.py") || !slices.Contains(got, `PythonPath=C:\QGIS\python`) {
		t.Errorf("Unix names keep their case: %q", got)
	}
	if !slices.Contains(got, "UV_NATIVE_TLS=1") || slices.Contains(got, "UV_SYSTEM_CERTS=1") {
		t.Errorf("uv before 0.11 needs UV_NATIVE_TLS: %q", got)
	}
	for _, set := range []string{"UV_NATIVE_TLS=0", "uv_system_certs=false"} {
		got = serverEnv("windows", append(environ, set), "uv 0.11.2")
		if slices.Contains(got, "UV_SYSTEM_CERTS=1") || slices.Contains(got, "UV_NATIVE_TLS=1") {
			t.Errorf("the user's %s was overridden: %q", set, got)
		}
	}
}

func TestWindowsProxySettingsBecomeProxyVariables(t *testing.T) {
	env := func(vars ...string) func(string) string {
		return func(name string) string {
			for _, kv := range vars {
				if k, v, _ := strings.Cut(kv, "="); k == name {
					return v
				}
			}
			return ""
		}
	}
	direct := "NO_PROXY=127.0.0.1,localhost,::1"
	for _, c := range []struct {
		environ          []string
		server, override string
		want             []string
	}{
		{nil, "proxy.corp:8080", "<local>;*.corp.example;10.*;intranet",
			[]string{"HTTPS_PROXY=http://proxy.corp:8080", "HTTP_PROXY=http://proxy.corp:8080", direct + ",.corp.example,intranet"}},
		{nil, "http=web:80;https=secure:443;ftp=files:21", "",
			[]string{"HTTPS_PROXY=http://secure:443", "HTTP_PROXY=http://web:80", direct}},
		{[]string{"NO_PROXY=.internal"}, "http=web:80", "",
			[]string{"HTTP_PROXY=http://web:80", direct + ",.internal"}},
		{nil, "socks=socks:1080", "", nil},
		{nil, "", "", nil},
		{[]string{"HTTPS_PROXY=http://mine:3128"}, "proxy.corp:8080", "", nil},
	} {
		if got := proxyEnv(env(c.environ...), c.server, c.override); !reflect.DeepEqual(got, c.want) {
			t.Errorf("proxyEnv(%q, %q, %q):\n got %q\nwant %q", c.environ, c.server, c.override, got, c.want)
		}
	}
}

func TestASecondLaunchShowsTheFirstInsteadOfStarting(t *testing.T) {
	home := t.TempDir()
	root := filepath.Join(home, "app files")
	unlock, url := claimInstance(home, root, time.Second)
	if unlock == nil || url != "" {
		t.Fatalf("first launch: unlock=%v url=%q", unlock != nil, url)
	}
	if again, url := claimInstance(home, root, 300*time.Millisecond); again != nil || url != "" {
		t.Fatal("a second launch claimed the app files while the first had not noted its address yet")
	}
	if other, _ := claimInstance(home, filepath.Join(home, "other app files"), time.Second); other == nil {
		t.Error("other app files waited for this launcher")
	} else {
		other()
	}
	first := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]string{"app": "twinstore-launcher", "root": root})
	}))
	defer first.Close()
	found := make(chan string, 1)
	go func() {
		again, url := claimInstance(home, root, 5*time.Second)
		if again != nil {
			again()
			url = "claimed"
		}
		found <- url
	}()
	time.Sleep(100 * time.Millisecond)
	saveInstance(home, root, first.URL)
	if url := <-found; url != first.URL {
		t.Errorf("waiting second launch got %q; want the first launcher at %s", url, first.URL)
	}
	clearInstance(home, first.URL)
	unlock()
	if again, _ := claimInstance(home, root, time.Second); again == nil {
		t.Error("the lock outlived its launcher")
	} else {
		again()
	}
}

func TestAppFoldersCompareAsTheFileSystemDoes(t *testing.T) {
	a, b := `C:\Users\Me\TwinStore\app`, `c:\users\me\twinstore\APP`
	if !sameRoot("windows", a, b) || sameRoot("windows", a, a+"2") {
		t.Error("Windows folders compare ignoring case only")
	}
	if sameRoot("linux", "/home/me/App", "/home/me/app") || !sameRoot("linux", "/home/me/app", "/home/me/app") {
		t.Error("Unix folders compare exactly")
	}
}
