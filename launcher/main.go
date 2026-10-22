// Command twinstore is the one-click launcher: double-click the TwinStore icon and the app opens
// in the browser, on Windows, macOS and Linux alike.
//
// It finds the app files next to it (or inside the macOS app bundle), fetches uv on first run (uv
// brings Python and every dependency), starts the server, and shows a boot screen at
// http://127.0.0.1:8000 until the app is ready — then serves the app at that same address.
// Clicking the icon again reopens the running app. Quit from the app (⌘K → Quit TwinStore), from
// the boot screen, or with Ctrl+C when started from a terminal.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"
)

var version = "dev" // set with -ldflags "-X main.version=…"

type options struct {
	port      int
	noBrowser bool
	smoke     bool
	rebuildUI bool
}

func main() {
	var opt options
	flag.IntVar(&opt.port, "port", 8000, "preferred address port (the next free one is used if taken)")
	flag.BoolVar(&opt.noBrowser, "no-browser", false, "do not open a browser tab")
	flag.BoolVar(&opt.smoke, "smoke", false, "start, wait until the app answers, then quit (for CI)")
	flag.BoolVar(&opt.rebuildUI, "rebuild-ui", false, "rebuild the web interface before starting")
	showVersion := flag.Bool("version", false, "print the version and exit")
	flag.Parse()
	if *showVersion {
		fmt.Println("twinstore launcher", version)
		return
	}
	if detachFromBundle() { // macOS: the app bundle returns at once, the launcher keeps running
		return
	}
	os.Exit(run(opt))
}

func run(opt options) int {
	proxy := useSystemProxy() // before any web request: Go reads the proxy variables once
	home, err := appHome()
	if err != nil {
		fmt.Fprintln(os.Stderr, "TwinStore:", err)
		return 1
	}
	root, rootErr := findRoot()
	if rootErr == nil && !opt.smoke {
		unlock, url := claimInstance(home, root, 20*time.Second)
		if unlock == nil { // already running: just show it
			if url == "" {
				fmt.Fprintln(os.Stderr, "TwinStore: another launcher for these app files is starting but does not answer")
				return 1
			}
			if isTerminal() {
				fmt.Println("TwinStore is already running at", url)
			}
			if !opt.noBrowser {
				openBrowser(url)
			}
			return 0
		}
		defer unlock()
	}
	logs := newLog(filepath.Join(home, "logs"), isTerminal())
	defer logs.Close()
	logs.Printf("TwinStore launcher %s", version)
	if proxy != "" {
		logs.Printf("Using the proxy set in Windows: %s", proxy)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	app := newApp(home, root, opt, logs)
	srv, err := app.listen(opt.port)
	if err != nil {
		logs.Printf("Cannot open a local port: %v", err)
		return 1
	}
	defer srv.Close()
	logs.Printf("Boot screen at %s", app.url)
	if rootErr != nil {
		app.status.fail("files", rootErr.Error())
	} else {
		saveInstance(home, root, app.url)
		defer clearInstance(home, app.url)
		if isLinux() && !opt.smoke {
			installDesktopEntry(home, logs)
		}
		go app.start()
	}
	if !opt.noBrowser {
		openBrowser(app.url)
	}

	select {
	case <-ctx.Done():
	case <-app.quit:
	case code := <-app.smokeDone:
		app.stopBackend(10 * time.Second)
		return code
	}
	logs.Printf("Stopping TwinStore…")
	app.stopBackend(10 * time.Second)
	logs.Printf("Stopped.")
	return 0
}
