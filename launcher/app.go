package main

import (
	"bufio"
	"cmp"
	"errors"
	"fmt"
	"hash/crc32"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// nodeWheel is the Node.js package uv adds when the web interface has to be built from source.
const nodeWheel = "nodejs-wheel-binaries==24.19.0"

type app struct {
	home, root string
	opt        options
	log        *logger
	status     *status
	url        string // the address the browser uses (this launcher)

	target     atomic.Pointer[url.URL] // the server, once it answers
	starting   atomic.Bool
	restarting atomic.Bool
	quit       chan struct{}
	quitOnce   sync.Once
	smokeDone  chan int

	mu       sync.Mutex
	cmd      *exec.Cmd
	stdin    io.WriteCloser
	exited   chan struct{}
	stopping bool
}

func newApp(home, root string, opt options, logs *logger) *app {
	return &app{
		home: home, root: root, opt: opt, log: logs, status: newStatus(),
		quit: make(chan struct{}), smokeDone: make(chan int, 1),
	}
}

func (a *app) requestQuit() { a.quitOnce.Do(func() { close(a.quit) }) }

// retry starts the app again after a failure. A server that is still running but has not answered (the error after
// stuckStart) is stopped first; a start in progress is left alone.
func (a *app) retry() {
	if !a.running() {
		a.start()
		return
	}
	if !a.restarting.CompareAndSwap(false, true) {
		return
	}
	defer a.restarting.Store(false)
	if a.status.view().Error == "" {
		return
	}
	a.log.Printf("Restarting the server")
	a.stopBackend(10 * time.Second)
	a.start()
}

// dataHome is where projects and the Python environment live when the app files cannot hold
// them (read-only macOS bundle); "" keeps the usual backend/.data next to the app.
func (a *app) dataHome() string {
	if inBundle(a.root) || !writable(filepath.Join(a.root, "backend")) {
		return a.home
	}
	return ""
}

// shortVenv is where the Python environment goes on Windows when the app folder's path is long: package files
// nest deep (about 130 more characters under the environment), and past 260 characters Windows without long
// paths enabled cannot write their bytecode or import them. "" keeps backend/.venv.
func (a *app) shortVenv() string { return shortVenvFor(runtime.GOOS, a.root, a.home) }

func shortVenvFor(goos, root, home string) string {
	if goos != "windows" || len(root)+len(`\backend\.venv`) <= 90 {
		return ""
	}
	return filepath.Join(home, "venv", fmt.Sprintf("%08x", crc32.ChecksumIEEE([]byte(strings.ToLower(root)))))
}

func (a *app) start() {
	if !a.starting.CompareAndSwap(false, true) {
		return
	}
	defer a.starting.Store(false)
	if a.running() {
		return
	}
	a.status.reset()
	a.status.done("files", a.root)
	uv, version := findUV(a.home)
	if !uvAtLeast(version, minUV) {
		if uv != "" {
			a.log.Printf("%s is too old (%s); fetching a current uv", uv, cmp.Or(version, "no version"))
		}
		a.status.activate("uv", "Downloading uv — one time, about 20 MB")
		fetched, err := installUV(a.home, a.log.Printf)
		switch {
		case err == nil:
			uv, version = fetched, uvVersion(fetched)
		case version != "": // offline: the older uv may still do
			a.log.Printf("uv: %v; trying %s", err, uv)
		default:
			a.log.Printf("uv: %v", err)
			a.status.fail("uv", "Could not fetch uv: "+err.Error())
			a.smokeFail()
			return
		}
	}
	a.status.done("uv", version)
	a.log.Printf("Using %s", uv)
	if err := a.launch(uv, version); err != nil {
		a.log.Printf("start failed: %v", err)
		a.status.fail("python", "Could not start the app: "+err.Error())
		a.smokeFail()
	}
}

func uvVersion(uv string) string {
	cmd := exec.Command(uv, "--version")
	setupProcess(cmd)
	out, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

func freePort() (int, error) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	defer ln.Close()
	return ln.Addr().(*net.TCPAddr).Port, nil
}

// pythonOverrides are settings another Python leaves system-wide (ArcGIS, QGIS, old installers on Windows): they
// point the server's Python at that installation's standard library or packages, or run its startup script first.
var pythonOverrides = []string{"PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP"}

// serverEnv is the environment uv and the server run with: environ without pythonOverrides, plus extra.
func serverEnv(goos string, environ []string, uvVer string, extra ...string) []string {
	env := make([]string, 0, len(environ)+len(extra)+1)
	for _, kv := range environ {
		if !slices.ContainsFunc(pythonOverrides, func(name string) bool { return setsEnv(goos, kv, name) }) {
			env = append(env, kv)
		}
	}
	// uv checks certificates against its own list, so behind a network that inspects HTTPS it fails with
	// "invalid peer certificate: UnknownIssuer" where Go, which trusts the system's list, fetched uv fine. uv 0.11
	// renamed UV_NATIVE_TLS and warns on every run when it is set; a choice the user made either way stands.
	tls := "UV_SYSTEM_CERTS"
	if uvRelease.MatchString(uvVer) && !uvAtLeast(uvVer, [2]int{0, 11}) {
		tls = "UV_NATIVE_TLS"
	}
	if !slices.ContainsFunc(env, func(kv string) bool {
		return setsEnv(goos, kv, "UV_SYSTEM_CERTS") || setsEnv(goos, kv, "UV_NATIVE_TLS")
	}) {
		env = append(env, tls+"=1")
	}
	return append(env, extra...)
}

// setsEnv reports whether kv ("NAME=value") sets the variable name; Windows names ignore case.
func setsEnv(goos, kv, name string) bool {
	k, _, _ := strings.Cut(kv, "=")
	return k == name || goos == "windows" && strings.EqualFold(k, name)
}

func (a *app) launch(uv, version string) error {
	port, err := freePort()
	if err != nil {
		return err
	}
	dist := filepath.Join(a.root, "frontend", "dist")
	// The tested Python: uv would otherwise fetch the newest one, where some dependencies have no wheels yet.
	// --no-dev: the test and type-check tools are for development, not for running the app.
	args := []string{"run", "--project", filepath.Join(a.root, "backend"), "--frozen", "--no-dev", "--python", "3.13"}
	if !fileExists(filepath.Join(dist, ".prebuilt")) && fileExists(filepath.Join(a.root, "frontend", "package.json")) {
		args = append(args, "--with", nodeWheel)
	}
	args = append(args, "python", "-m", "store_emulator.launcher",
		"--no-browser", "--host", "127.0.0.1", "--port", strconv.Itoa(port), "--exit-with-stdin")
	if a.opt.rebuildUI {
		args = append(args, "--rebuild-ui")
	}
	cmd := exec.Command(uv, args...)
	cmd.Dir = a.root
	// UV_COMPILE_BYTECODE: compile the packages in parallel while they install, shown as its own step, instead of one
	// file at a time during the server's first import (minutes on a computer that scans every new file).
	// PYTHONUTF8: files are read and written as UTF-8 whatever the Windows code page (cp949, cp1252, …).
	cmd.Env = serverEnv(runtime.GOOS, os.Environ(), version, "PYTHONUNBUFFERED=1", "PYTHONIOENCODING=utf-8", "PYTHONUTF8=1",
		"UV_NO_PROGRESS=1", "NO_COLOR=1", "UV_COMPILE_BYTECODE=1")
	if data := a.dataHome(); data != "" {
		cmd.Env = append(cmd.Env, "PARASTORE_DATA_HOME="+data, "UV_PROJECT_ENVIRONMENT="+filepath.Join(data, "venv"), "PYTHONDONTWRITEBYTECODE=1")
		a.log.Printf("Data folder: %s", filepath.Join(data, ".data"))
	} else if venv := a.shortVenv(); venv != "" {
		cmd.Env = append(cmd.Env, "UV_PROJECT_ENVIRONMENT="+venv)
		a.log.Printf("Python environment: %s (the app folder's path is long)", venv)
	}
	setupProcess(cmd)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return err
	}
	pr, pw := io.Pipe()
	cmd.Stdout, cmd.Stderr = pw, pw
	a.log.Printf("Starting: uv %s", strings.Join(args, " "))
	a.status.activate("python", "Checking the Python environment")
	if err := cmd.Start(); err != nil {
		return err
	}
	exited := make(chan struct{})
	a.mu.Lock()
	a.cmd, a.stdin, a.exited, a.stopping = cmd, stdin, exited, false
	a.mu.Unlock()

	go a.readOutput(pr, exited)
	go func() {
		err := cmd.Wait()
		// What the server started in its process group ends with it: left running, llama-server keeps gigabytes of
		// memory, Try again takes it for a model server started outside the app, and Quit never stops it.
		killGroup(cmd)
		pw.Close()
		a.mu.Lock()
		defer a.mu.Unlock()
		// Publish the exit only after cleanup, before allowing another start.
		defer close(exited)
		if a.exited != exited {
			return
		}
		a.target.Store(nil)
		if a.stopping {
			return
		}
		code := -1
		var exit *exec.ExitError
		if errors.As(err, &exit) {
			code = exit.ExitCode()
		} else if err == nil {
			code = 0
		}
		a.log.Printf("The app stopped (exit code %d)", code)
		a.status.fail(a.status.current(), fmt.Sprintf("TwinStore stopped unexpectedly (exit code %d). The log below shows why.", code))
		a.smokeFail()
	}()
	return nil
}

var startingOn = regexp.MustCompile(`Starting on (http://[0-9.:a-z]+)`)

// readOutput follows the server's console output and moves the boot screen along.
func (a *app) readOutput(r io.Reader, exited <-chan struct{}) {
	br := bufio.NewReaderSize(r, 64*1024)
	for {
		raw, err := readLine(br, 64*1024)
		if err != nil && raw == "" {
			return
		}
		line := strings.TrimSpace(raw)
		if line == "" {
			continue
		}
		a.log.Line(line)
		a.mu.Lock()
		if !a.backendActiveLocked(exited) {
			a.mu.Unlock()
			continue
		}
		switch {
		case strings.Contains(line, "Preparing the web interface"):
			a.status.done("python", "ready")
			a.status.activate("ui", "Building once with Node.js — 1 to 3 minutes")
		case strings.Contains(line, "Web interface ready"):
			a.status.done("ui", "built")
		case strings.HasPrefix(line, "Installed ") && a.status.state("python") == "active":
			a.status.activate("python", line+" — preparing them for a fast start")
		case strings.Contains(line, "Building the web interface failed"):
			a.status.done("ui", "build failed — serving the API only")
		case startingOn.MatchString(line):
			if a.status.state("ui") == "pending" {
				a.status.done("ui", "up to date")
			}
			a.status.done("python", "ready")
			a.status.activate("server", "Waking up the shoppers")
			go a.waitReady(startingOn.FindStringSubmatch(line)[1], exited)
		case a.status.state("python") == "active" && !strings.HasPrefix(line, "[TwinStore]"):
			if len(line) > 90 {
				line = line[:87] + "…"
			}
			a.status.activate("python", line)
		}
		a.mu.Unlock()
	}
}

// readLine reads one line of the server's output and keeps at most max bytes of it. A very long line (a
// logged picture, say) must not stop the reading: the server would then block on a full pipe and hang.
func readLine(br *bufio.Reader, max int) (string, error) {
	var buf []byte
	for {
		part, more, err := br.ReadLine()
		if room := max - len(buf); room > 0 {
			buf = append(buf, part[:min(len(part), room)]...)
		}
		if err != nil || !more {
			return string(buf), err
		}
	}
}

// backendActiveLocked requires a.mu, so readiness and exit publication are atomic.
func (a *app) backendActiveLocked(exited <-chan struct{}) bool {
	if a.exited != exited || a.stopping {
		return false
	}
	select {
	case <-exited:
		return false
	default:
		return true
	}
}

// A first start can import for minutes while the computer scans thousands of new files. The boot screen says so
// after slowStart; after stuckStart it shows an error with Try again, but keeps listening while the server runs.
var (
	slowStart  = 90 * time.Second
	stuckStart = 15 * time.Minute
)

func (a *app) waitReady(base string, exited <-chan struct{}) {
	target, err := url.Parse(base)
	if err != nil {
		a.status.fail("server", "Bad server address "+base)
		return
	}
	client := http.Client{Timeout: 2 * time.Second}
	started := time.Now()
	slow, stuck := false, false
	for {
		a.mu.Lock()
		active := a.backendActiveLocked(exited)
		a.mu.Unlock()
		if !active {
			return
		}
		resp, err := client.Get(base + "/api/health")
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				a.mu.Lock()
				if !a.backendActiveLocked(exited) {
					a.mu.Unlock()
					return
				}
				a.target.Store(target)
				a.status.finish()
				a.mu.Unlock()
				a.log.Printf("TwinStore is ready at %s", a.url)
				if a.opt.smoke {
					a.smokeCheck()
				}
				return
			}
		}
		waited := time.Since(started)
		a.mu.Lock()
		if a.backendActiveLocked(exited) {
			switch {
			case !stuck && waited >= stuckStart:
				stuck = true
				a.status.fail("server", fmt.Sprintf("The server has not answered for %d minutes. The log below shows "+
					"its last step; Try again restarts it.", int(waited.Minutes())))
				a.log.Printf("The server has not answered after %s; still waiting", waited.Round(time.Second))
				a.smokeFail()
			case !slow && waited >= slowStart:
				slow = true
				a.status.activate("server", "Still loading. A first start can take several minutes while the "+
					"computer scans the new files")
				a.log.Printf("The server has not answered after %s; a first start can take several minutes",
					waited.Round(time.Second))
			}
		}
		a.mu.Unlock()
		select {
		case <-exited:
			return
		case <-time.After(400 * time.Millisecond):
		}
	}
}

// smokeCheck asks for the health check and the interface through the launcher's own address.
func (a *app) smokeCheck() {
	client := http.Client{Timeout: 10 * time.Second}
	for _, path := range []string{"/api/health", "/"} {
		resp, err := client.Get(a.url + path)
		if err != nil || resp.StatusCode != http.StatusOK {
			a.log.Printf("smoke: %s failed (%v)", path, err)
			a.smokeDone <- 1
			return
		}
		resp.Body.Close()
		a.log.Printf("smoke: %s OK", path)
	}
	a.smokeDone <- 0
}

func (a *app) smokeFail() {
	if a.opt.smoke {
		select {
		case a.smokeDone <- 1:
		default:
		}
	}
}

func (a *app) running() bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.exited == nil {
		return false
	}
	select {
	case <-a.exited:
		return false
	default:
		return true
	}
}

// stopBackend closes the server's stdin (it shuts down cleanly on end of input), then ends the
// whole process tree if it is still running after half the timeout.
func (a *app) stopBackend(timeout time.Duration) {
	a.mu.Lock()
	cmd, stdin, exited := a.cmd, a.stdin, a.exited
	a.stopping = true
	a.mu.Unlock()
	a.target.Store(nil)
	if cmd == nil || exited == nil {
		return
	}
	stdin.Close()
	select {
	case <-exited:
		return
	case <-time.After(timeout / 2):
	}
	a.log.Printf("Ending the server processes")
	killTree(cmd)
	select {
	case <-exited:
	case <-time.After(timeout / 2):
	}
}
