package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// logger writes the launcher's and the server's output to logs/launcher.log (the previous run
// is kept as launcher.prev.log), echoes it to the terminal when there is one, and keeps the
// last lines for the boot screen.
type logger struct {
	mu   sync.Mutex
	file *os.File
	path string
	echo bool
	ring []string
}

const ringSize = 400

func newLog(dir string, echo bool) *logger {
	l := &logger{echo: echo, path: filepath.Join(dir, "launcher.log")}
	if os.MkdirAll(dir, 0o755) == nil {
		_ = os.Rename(l.path, filepath.Join(dir, "launcher.prev.log"))
		l.file, _ = os.Create(l.path)
	}
	return l
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
