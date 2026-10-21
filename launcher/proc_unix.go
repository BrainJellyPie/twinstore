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
