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
	// macOS: the app bundle returns at once, the launcher keeps running (not for --smoke, whose exit code is the result)
	if !opt.smoke && detachFromBundle() {
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
	// Before any log turns over: the logs name the data folders earlier versions used (see bringStoresOver).
	rememberEarlierData(home)
	// Before the log turns over and the address is taken: a second click only shows the running app, and another
	// version that quits for this one leaves its address free (bookmarks keep working).
	var held claim
	if rootErr == nil {
		if opt.smoke {
			held = smokeClaim(dataHomeOf(home, root))
		} else if held = claimData(home, dataHomeOf(home, root), root, claimWait); held.url != "" {
			if isTerminal() { // already running: just show it
				fmt.Println("TwinStore is already running at", held.url)
			}
			if !opt.noBrowser {
				openBrowser(held.url)
			}
			return 0
		}
	}
	// Only the launcher that holds the per-user data folder turns over launcher.log (see openLog).
	logs := openLog(filepath.Join(home, "logs"), isTerminal(), held.unlock != nil && dataHomeOf(home, root) == home)
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
		return 1 // the lock goes with the process
	}
	defer app.releaseData() // after the server has stopped (deferred calls run last first)
	defer srv.Close()
	logs.Printf("Boot screen at %s", app.url)
	switch {
	case rootErr != nil:
		app.status.fail("files", rootErr.Error())
		app.smokeFail()
	case opt.smoke: // the stores are this launcher's if no other one holds them; it never asks one to quit
		app.holdForSmoke(held.unlock)
		go app.start()
	default:
		if isLinux() {
			installDesktopEntry(home, logs)
		}
		// Otherwise the boot screen says who uses the stores (or that the one holding them does not answer), with
		// Try again.
		if app.useClaim(held) {
			go app.start()
		}
	}
	if !opt.noBrowser {
		openBrowser(app.url)
	}

	select {
	case <-ctx.Done():
	case <-app.quit:
	case code := <-app.smokeDone:
		app.quitting.Store(true)
		app.stopBackend(10 * time.Second)
		return code
	}
	app.quitting.Store(true) // a click on the icon now waits until this one has let go of the stores
	logs.Printf("Stopping TwinStore…")
	app.stopBackend(10 * time.Second)
	logs.Printf("Stopped.")
	return 0
}
