package main

import (
	"context"
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/http/httputil"
	"strings"
	"time"
)

//go:embed boot.html
var bootPage []byte

//go:embed icon/twinstore.png
var iconPNG []byte

// listen opens the browser-facing address: the preferred port, the next free one after it, or
// any free port.
func (a *app) listen(preferred int) (*http.Server, error) {
	var ln net.Listener
	var err error
	for p := preferred; p < preferred+20 && ln == nil; p++ {
		ln, err = net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", p))
	}
	if ln == nil {
		if ln, err = net.Listen("tcp", "127.0.0.1:0"); err != nil {
			return nil, err
		}
	}
	a.url = fmt.Sprintf("http://127.0.0.1:%d", ln.Addr().(*net.TCPAddr).Port)
	srv := &http.Server{Handler: a.handler(), ReadHeaderTimeout: 15 * time.Second}
	go func() {
		if err := srv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			a.log.Printf("server: %v", err)
		}
	}()
	return srv, nil
}

func (a *app) handler() http.Handler {
	proxy := &httputil.ReverseProxy{
		Rewrite: func(pr *httputil.ProxyRequest) {
			if t := a.target.Load(); t != nil {
				pr.SetURL(t)
			}
		},
		FlushInterval: -1, // stream server-sent events and long responses as they come
		// The server's CORS answers are for the development UI on another port; through this address only this
		// address's pages may use it (crossSite turns other pages away), so none are passed on.
		ModifyResponse: func(resp *http.Response) error {
			for name := range resp.Header {
				if strings.HasPrefix(name, "Access-Control-") {
					resp.Header.Del(name)
				}
			}
			return nil
		},
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			if errors.Is(err, context.Canceled) {
				return
			}
			a.log.Printf("proxy: %s %s: %v", r.Method, r.URL.Path, err)
			http.Error(w, "TwinStore is not answering right now", http.StatusBadGateway)
		},
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /__twinstore/ping", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]any{"app": "twinstore-launcher", "version": version, "root": a.root,
			"ready": a.target.Load() != nil, "stopping": a.quitting.Load()})
	})
	mux.HandleFunc("GET /__twinstore/status", func(w http.ResponseWriter, r *http.Request) {
		v := a.status.view()
		v.Log, v.Root, v.Data, v.LogFile = a.log.Tail(160), a.root, a.dataFolder(), a.log.path
		v.CanRetry = a.root != "" // without the app files there is nothing to try again
		writeJSON(w, v)
	})
	mux.HandleFunc("GET /__twinstore/log", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		raw, err := a.log.Contents()
		if err != nil {
			raw = []byte(strings.Join(a.log.Tail(ringSize), "\n"))
		}
		w.Write(raw)
	})
	mux.HandleFunc("GET /__twinstore/icon.png", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "image/png")
		w.Header().Set("Cache-Control", "max-age=86400")
		w.Write(iconPNG)
	})
	mux.HandleFunc("POST /__twinstore/quit", sameSite(func(w http.ResponseWriter, r *http.Request) {
		a.quitting.Store(true) // a click on the icon now waits for this one to let go instead of showing it
		writeJSON(w, map[string]bool{"stopping": true})
		go func() { time.Sleep(200 * time.Millisecond); a.requestQuit() }()
	}))
	mux.HandleFunc("POST /__twinstore/retry", sameSite(func(w http.ResponseWriter, r *http.Request) {
		if a.root != "" {
			go a.retry()
		}
		writeJSON(w, map[string]bool{"restarting": true})
	}))
	mux.HandleFunc("POST /__twinstore/skip-data", sameSite(func(w http.ResponseWriter, r *http.Request) {
		if a.root != "" {
			a.skipData.Store(true)
			go a.retry()
		}
		writeJSON(w, map[string]bool{"restarting": true})
	}))
	// The launcher's own paths never go on to the server: its CORS answer to a preflight would let other web pages
	// send the X-TwinStore header (see sameSite).
	mux.HandleFunc("/__twinstore/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		http.NotFound(w, r)
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if a.target.Load() != nil {
			proxy.ServeHTTP(w, r)
			return
		}
		if r.Method == http.MethodGet && (r.URL.Path == "/" || strings.Contains(r.Header.Get("Accept"), "text/html")) {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			w.Header().Set("Cache-Control", "no-store")
			w.Write(bootPage)
			return
		}
		w.Header().Set("Retry-After", "2")
		http.Error(w, `{"detail":"TwinStore is starting"}`, http.StatusServiceUnavailable)
	})
	return localOnly(crossSite(mux))
}

// localOnly answers only requests addressed to this machine by name (no DNS-rebinding tricks).
func localOnly(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		host, _, err := net.SplitHostPort(r.Host)
		if err != nil {
			host = r.Host
		}
		if host != "127.0.0.1" && host != "localhost" && host != "::1" {
			http.Error(w, "TwinStore only answers on 127.0.0.1", http.StatusForbidden)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// crossSite turns away what other web pages send here: a request naming another origin (a fetch, a form posted from
// another site, a CORS preflight) or one a browser marks cross-site that is not a plain visit (an image, a script).
// Without this any site the user visits could use the stores, the model keys' settings and Quit through this address
// (the server's CORS answer to a preflight let it send the X-TwinStore header). Programs that send neither header, and
// links to the app, still work.
func crossSite(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if origin := r.Header.Get("Origin"); origin != "" && !strings.EqualFold(origin, "http://"+r.Host) ||
			r.Header.Get("Sec-Fetch-Site") == "cross-site" && r.Header.Get("Sec-Fetch-Mode") != "navigate" {
			http.Error(w, "TwinStore answers only its own pages", http.StatusForbidden)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// sameSite requires the X-TwinStore header, which other web pages cannot send without a CORS
// preflight, which crossSite turns away and the launcher never approves.
func sameSite(h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-TwinStore") != "1" {
			http.Error(w, "missing X-TwinStore header", http.StatusForbidden)
			return
		}
		h(w, r)
	}
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	json.NewEncoder(w).Encode(v)
}
