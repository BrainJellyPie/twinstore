//go:build !windows

package main

import (
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestUnexpectedExitEndsWhatTheServerStarted(t *testing.T) {
	a, dir := testLauncher(t)
	for _, file := range []string{"release", "fail-run", "with-model-server"} {
		if err := os.WriteFile(filepath.Join(dir, file), nil, 0o600); err != nil {
			t.Fatal(err)
		}
	}
	a.start()
	waitForLauncher(t, func() bool { return !a.running() && a.status.view().Error != "" })
	files, _ := filepath.Glob(filepath.Join(dir, "model-*"))
	if len(files) != 1 {
		t.Fatalf("model server markers: %q", files)
	}
	port, err := os.ReadFile(files[0])
	if err != nil {
		t.Fatal(err)
	}
	for deadline := time.Now().Add(5 * time.Second); ; {
		conn, err := net.DialTimeout("tcp", "127.0.0.1:"+string(port), 200*time.Millisecond)
		if err != nil {
			return
		}
		conn.Close()
		if time.Now().After(deadline) {
			t.Fatal("the model server outlived the server that started it")
		}
		time.Sleep(20 * time.Millisecond)
	}
}
