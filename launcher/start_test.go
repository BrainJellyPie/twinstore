package main

import (
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"
)

// A copy of this test executable stands in for uv. It never starts Python or downloads anything.
func TestMain(m *testing.M) {
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
			fmt.Println("uv test")
		} else if fileExists(filepath.Join(dir, "fail-run")) {
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
		files, _ := filepath.Glob(filepath.Join(dir, "run-*"))
		for _, file := range files {
			pid, _ := strconv.Atoi(strings.TrimPrefix(filepath.Base(file), "run-"))
			if process, err := os.FindProcess(pid); err == nil {
				_ = process.Kill()
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
