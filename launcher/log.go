package main

import (
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// logger writes the launcher's and the server's output to its log file, echoes it to the terminal when there is
// one, and keeps the last lines for the boot screen.
type logger struct {
	mu   sync.Mutex
	file *os.File
	path string
	echo bool
	ring []string
}

const ringSize = 400

// pidLogAge is how long the logs of launchers that did not hold the stores are kept.
const pidLogAge = 7 * 24 * time.Hour

// newLog opens logs/launcher.log, keeping the previous run's as launcher.prev.log.
func newLog(dir string, echo bool) *logger { return openLog(dir, echo, true) }

// openLog opens the launcher's log. Only the launcher that holds the per-user data folder (main) turns over
// launcher.log; any other (app files not found, another launcher holding the stores, a data folder of the user's
// choosing, --smoke beside a running app) writes launcher.pid-<pid>.log. Turning over the log of a launcher that is
// still running moves it away under it, and on Windows, where the rename fails, would empty it.
func openLog(dir string, echo, main bool) *logger {
	l := &logger{echo: echo, path: filepath.Join(dir, "launcher.log")}
	if os.MkdirAll(dir, 0o755) != nil {
		return l
	}
	if main {
		// Windows cannot rename a file another program has open: an earlier launcher still running.
		if err := os.Rename(l.path, filepath.Join(dir, "launcher.prev.log")); err != nil && !errors.Is(err, fs.ErrNotExist) {
			main = false
		}
	}
	if main {
		removeOldLogs(dir)
	} else {
		l.path = filepath.Join(dir, fmt.Sprintf("launcher.pid-%d.log", os.Getpid()))
	}
	l.file, _ = os.Create(l.path)
	return l
}

// removeOldLogs deletes the logs of launchers that did not hold the stores, once they are a week old (one still
// open on Windows stays).
func removeOldLogs(dir string) {
	old, _ := filepath.Glob(filepath.Join(dir, "launcher.pid-*.log"))
	for _, path := range old {
		if st, err := os.Stat(path); err == nil && time.Since(st.ModTime()) > pidLogAge {
			_ = os.Remove(path)
		}
	}
}

// Contents is this launcher's own log, read through the file it writes, whatever another launcher did to its name.
func (l *logger) Contents() ([]byte, error) {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.file == nil {
		return nil, os.ErrNotExist
	}
	st, err := l.file.Stat()
	if err != nil {
		return nil, err
	}
	raw := make([]byte, st.Size())
	n, err := l.file.ReadAt(raw, 0)
	if errors.Is(err, io.EOF) {
		err = nil
	}
	return raw[:n], err
}

func (l *logger) Printf(format string, args ...any) {
	l.Line("» " + fmt.Sprintf(format, args...))
}

func (l *logger) Line(s string) {
	s = strings.TrimRight(s, "\r\n")
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.file != nil {
		fmt.Fprintf(l.file, "%s %s\n", time.Now().Format("15:04:05"), s)
	}
	if l.echo {
		fmt.Println(s)
	}
	l.ring = append(l.ring, s)
	if len(l.ring) > ringSize {
		l.ring = l.ring[len(l.ring)-ringSize:]
	}
}

func (l *logger) Tail(n int) []string {
	l.mu.Lock()
	defer l.mu.Unlock()
	if n > len(l.ring) {
		n = len(l.ring)
	}
	return append([]string(nil), l.ring[len(l.ring)-n:]...)
}

func (l *logger) Close() {
	l.mu.Lock()
	defer l.mu.Unlock()
	if l.file != nil {
		l.file.Close()
		l.file = nil
	}
}

func isTerminal() bool {
	st, err := os.Stdout.Stat()
	return err == nil && st.Mode()&os.ModeCharDevice != 0
}
