package main

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"reflect"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestReadinessResponseCannotReviveAnInactiveBackend(t *testing.T) {
	for _, mode := range []string{"exited", "stopping", "replaced"} {
		for _, code := range []int{http.StatusOK, http.StatusServiceUnavailable} {
			t.Run(mode+http.StatusText(code), func(t *testing.T) {
				dir := t.TempDir()
				logs := newLog(filepath.Join(dir, "logs"), false)
				defer logs.Close()
				a := newApp(dir, dir, options{}, logs)
				oldExited := make(chan struct{})
				a.exited = oldExited
				received, release := make(chan struct{}), make(chan struct{})
				var receivedOnce sync.Once
				server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					receivedOnce.Do(func() { close(received) })
					<-release
					w.WriteHeader(code)
				}))
				defer server.Close()
				done := make(chan struct{})
				go func() { a.waitReady(server.URL, oldExited); close(done) }()
				defer func() {
					a.mu.Lock()
					select {
					case <-a.exited:
					default:
						close(a.exited)
					}
					a.mu.Unlock()
					select {
					case <-done:
					case <-time.After(3 * time.Second):
						t.Error("health probe did not finish during cleanup")
					}
				}()
				select {
				case <-received:
				case <-time.After(3 * time.Second):
					close(release)
					t.Fatal("health probe did not start")
				}
				var wanted *url.URL
				switch mode {
				case "exited":
					close(oldExited)
				case "stopping":
					a.stopBackend(time.Millisecond)
					close(oldExited)
				case "replaced":
					close(oldExited)
					a.mu.Lock()
					a.exited = make(chan struct{})
					wanted, _ = url.Parse("http://127.0.0.1:54321")
					a.target.Store(wanted)
					a.mu.Unlock()
				}
				close(release)
				select {
				case <-done:
				case <-time.After(3 * time.Second):
					t.Fatal("inactive health probe did not stop")
				}
				if a.target.Load() != wanted {
					t.Error("late health response replaced the current backend target")
				}
				if a.status.view().Ready {
					t.Error("late health response marked an inactive backend ready")
				}
			})
		}
	}
}

func TestCurrentBackendBecomesReadyAfterTransientFailure(t *testing.T) {
	for _, transient := range []bool{false, true} {
		t.Run(map[bool]string{false: "immediate", true: "retry"}[transient], func(t *testing.T) {
			dir := t.TempDir()
			logs := newLog(filepath.Join(dir, "logs"), false)
			defer logs.Close()
			a := newApp(dir, dir, options{}, logs)
			exited := make(chan struct{})
			a.exited = exited
			defer close(exited)
			var calls atomic.Int32
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if calls.Add(1) == 1 && transient {
					w.WriteHeader(http.StatusServiceUnavailable)
					return
				}
				w.WriteHeader(http.StatusOK)
			}))
			defer server.Close()
			done := make(chan struct{})
			go func() { a.waitReady(server.URL, exited); close(done) }()
			select {
			case <-done:
			case <-time.After(3 * time.Second):
				t.Fatal("current backend did not become ready")
			}
			if a.target.Load() == nil || a.target.Load().String() != server.URL || !a.status.view().Ready {
				t.Fatal("current healthy backend was not published")
			}
			want := int32(1)
			if transient {
				want = 2
			}
			if calls.Load() != want {
				t.Errorf("health requests = %d; want %d", calls.Load(), want)
			}
		})
	}
}

func TestExitedBackendIsNotProbed(t *testing.T) {
	dir := t.TempDir()
	logs := newLog(filepath.Join(dir, "logs"), false)
	defer logs.Close()
	a := newApp(dir, dir, options{}, logs)
	exited := make(chan struct{})
	a.exited = exited
	close(exited)
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()
	a.waitReady(server.URL, exited)
	if calls.Load() != 0 || a.target.Load() != nil || a.status.view().Ready {
		t.Fatal("exited backend was probed or marked ready")
	}
}

func TestOldBackendOutputCannotOverwriteNewStartup(t *testing.T) {
	dir := t.TempDir()
	logs := newLog(filepath.Join(dir, "logs"), false)
	defer logs.Close()
	a := newApp(dir, dir, options{}, logs)
	a.exited = make(chan struct{})
	defer close(a.exited)
	oldExited := make(chan struct{})
	close(oldExited)
	a.status.activate("python", "New backend is starting")
	before := a.status.view()
	a.readOutput(strings.NewReader("Preparing the web interface\nWeb interface ready\nStarting on http://127.0.0.1:1\n"), oldExited)
	after := a.status.view()
	if !reflect.DeepEqual(before.Stages, after.Stages) || before.Error != after.Error || after.Ready {
		t.Fatal("old output changed the current startup status")
	}
}

func TestSlowFirstStartIsAwaitedPastTheStuckNotice(t *testing.T) {
	oldSlow, oldStuck := slowStart, stuckStart
	slowStart, stuckStart = 50*time.Millisecond, 150*time.Millisecond
	defer func() { slowStart, stuckStart = oldSlow, oldStuck }()
	dir := t.TempDir()
	logs := newLog(filepath.Join(dir, "logs"), false)
	defer logs.Close()
	a := newApp(dir, dir, options{}, logs)
	exited := make(chan struct{})
	a.exited = exited
	defer close(exited)
	var answering atomic.Bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !answering.Load() {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()
	done := make(chan struct{})
	go func() { a.waitReady(server.URL, exited); close(done) }()
	waitForLauncher(t, func() bool { return a.status.view().Error != "" })
	if a.status.state("server") != "error" {
		t.Fatal("a server that never answered was not reported")
	}
	answering.Store(true)
	select {
	case <-done:
	case <-time.After(3 * time.Second):
		t.Fatal("a late answer after the stuck notice was not picked up")
	}
	view := a.status.view()
	if !view.Ready || view.Error != "" || a.target.Load() == nil {
		t.Fatalf("late answer did not publish the server: ready=%v error=%q", view.Ready, view.Error)
	}
}
