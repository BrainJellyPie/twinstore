package main

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
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

	target    atomic.Pointer[url.URL] // the server, once it answers
	starting  atomic.Bool
	quit      chan struct{}
	quitOnce  sync.Once
	smokeDone chan int

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

// dataHome is where projects and the Python environment live when the app files cannot hold
// them (read-only macOS bundle); "" keeps the usual backend/.data next to the app.
func (a *app) dataHome() string {
	if inBundle(a.root) || !writable(filepath.Join(a.root, "backend")) {
		return a.home
	}
	return ""
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
	uv := findUV(a.home)
	if uv == "" {
		a.status.activate("uv", "Downloading uv — one time, about 20 MB")
		var err error
		if uv, err = installUV(a.home, a.log.Printf); err != nil {
			a.log.Printf("uv: %v", err)
			a.status.fail("uv", "Could not fetch uv: "+err.Error())
			a.smokeFail()
			return
		}
	}
	a.status.done("uv", uvVersion(uv))
	a.log.Printf("Using %s", uv)
	if err := a.launch(uv); err != nil {
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

func (a *app) launch(uv string) error {
	port, err := freePort()
	if err != nil {
		return err
	}
	dist := filepath.Join(a.root, "frontend", "dist")
	args := []string{"run", "--project", filepath.Join(a.root, "backend"), "--frozen"}
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
	cmd.Env = append(os.Environ(), "PYTHONUNBUFFERED=1", "PYTHONIOENCODING=utf-8", "UV_NO_PROGRESS=1", "NO_COLOR=1")
	if data := a.dataHome(); data != "" {
		cmd.Env = append(cmd.Env, "PARASTORE_DATA_HOME="+data, "UV_PROJECT_ENVIRONMENT="+filepath.Join(data, "venv"), "PYTHONDONTWRITEBYTECODE=1")
		a.log.Printf("Data folder: %s", filepath.Join(data, ".data"))
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

	go a.readOutput(pr)
	go func() {
		err := cmd.Wait()
		pw.Close()
		close(exited)
		a.target.Store(nil)
		a.mu.Lock()
		stopping := a.stopping
		a.mu.Unlock()
		if stopping {
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
func (a *app) readOutput(r io.Reader) {
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 64*1024), 1024*1024)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		a.log.Line(line)
		switch {
		case strings.Contains(line, "Preparing the web interface"):
			a.status.done("python", "ready")
			a.status.activate("ui", "Building once with Node.js — 1 to 3 minutes")
		case strings.Contains(line, "Web interface ready"):
			a.status.done("ui", "built")
		case strings.Contains(line, "Building the web interface failed"):
			a.status.done("ui", "build failed — serving the API only")
		case startingOn.MatchString(line):
			if a.status.state("ui") == "pending" {
				a.status.done("ui", "up to date")
			}
			a.status.done("python", "ready")
			a.status.activate("server", "Waking up the shoppers")
			go a.waitReady(startingOn.FindStringSubmatch(line)[1])
		case a.status.state("python") == "active" && !strings.HasPrefix(line, "[TwinStore]"):
			if len(line) > 90 {
				line = line[:87] + "…"
			}
			a.status.activate("python", line)
		}
	}
}

func (a *app) waitReady(base string) {
	target, err := url.Parse(base)
	if err != nil {
		a.status.fail("server", "Bad server address "+base)
		return
	}
	client := http.Client{Timeout: 2 * time.Second}
	deadline := time.Now().Add(3 * time.Minute)
	for time.Now().Before(deadline) {
		resp, err := client.Get(base + "/api/health")
		if err == nil {
			resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				a.target.Store(target)
				a.status.finish()
				a.log.Printf("TwinStore is ready at %s", a.url)
				if a.opt.smoke {
					a.smokeCheck()
				}
				return
			}
		}
		a.mu.Lock()
		exited := a.exited
		a.mu.Unlock()
		select {
		case <-exited:
			return
		case <-time.After(400 * time.Millisecond):
		}
	}
	a.status.fail("server", "The server did not answer within 3 minutes.")
	a.smokeFail()
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
