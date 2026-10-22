//go:build !windows

package main

import (
	"os"
	"os/exec"
	"runtime"
	"strings"
	"syscall"
	"time"
)

// setupProcess puts the server in its own process group so it can be ended with its children.
func setupProcess(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}

func killTree(cmd *exec.Cmd) {
	if cmd.Process == nil {
		return
	}
	pgid := -cmd.Process.Pid
	_ = syscall.Kill(pgid, syscall.SIGTERM)
	time.Sleep(2 * time.Second)
	_ = syscall.Kill(pgid, syscall.SIGKILL)
}

// killGroup ends what is left of the server's process group once the server itself has exited: the processes it
// started in its group, such as llama-server.
func killGroup(cmd *exec.Cmd) {
	if cmd.Process != nil {
		_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
	}
}

// tryLock takes an exclusive lock on path, which the system drops when this launcher ends, however it ends.
// busy: another launcher holds it. Where locks are not supported, unlock does nothing, as before the lock.
func tryLock(path string) (unlock func(), busy bool) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		return func() {}, false
	}
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		f.Close()
		return func() {}, err == syscall.EWOULDBLOCK
	}
	return func() { f.Close() }, false
}

// systemProxy is the proxy set in the system settings, read only on Windows: elsewhere desktop settings reach
// programs as the proxy variables.
func systemProxy() (server, override string) { return "", "" }

func openBrowser(url string) {
	if runtime.GOOS == "darwin" {
		_ = exec.Command("open", url).Start()
		return
	}
	for _, c := range [][]string{{"xdg-open"}, {"gio", "open"}, {"sensible-browser"}, {"x-www-browser"}} {
		if _, err := exec.LookPath(c[0]); err == nil {
			cmd := exec.Command(c[0], append(c[1:], url)...)
			if cmd.Start() == nil {
				go cmd.Wait()
				return
			}
		}
	}
}

// detachFromBundle restarts the launcher in the background when Finder starts it from the app
// bundle, so the bundle itself exits at once: macOS then lets a second click start it again,
// which reopens the running app instead of doing nothing.
func detachFromBundle() bool {
	exe, err := os.Executable()
	if runtime.GOOS != "darwin" || err != nil || os.Getenv("TWINSTORE_DETACHED") == "1" ||
		!strings.Contains(exe, ".app/Contents/MacOS/") || isTerminal() {
		return false
	}
	cmd := exec.Command(exe, os.Args[1:]...)
	cmd.Env = append(os.Environ(), "TWINSTORE_DETACHED=1")
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start() == nil
}
