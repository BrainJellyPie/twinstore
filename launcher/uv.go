package main

import (
	"archive/tar"
	"archive/zip"
	"cmp"
	"compress/gzip"
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"
)

// minUV is the oldest uv the launcher runs (major, minor): an older one, such as a `pip install uv` from 2024,
// may reject the lockfile (backend/uv.lock is revision 5, written by uv 0.11) or the options the launcher passes.
var minUV = [2]int{0, 11}

// findUV returns a uv already on this machine and its version: the copy the launcher fetched, else one on PATH or
// in the standard install folders, whichever comes first at minUV or newer. When none is that new, it returns the
// first one found, which start falls back to if a current uv cannot be fetched; "" when there is none.
func findUV(home string) (uv, version string) {
	user, _ := os.UserHomeDir()
	candidates := []string{filepath.Join(home, "bin", exeName("uv"))}
	if p, err := exec.LookPath("uv"); err == nil {
		candidates = append(candidates, p)
	}
	for _, dir := range []string{filepath.Join(user, ".local", "bin"), filepath.Join(user, ".cargo", "bin")} {
		candidates = append(candidates, filepath.Join(dir, exeName("uv")))
	}
	return pickUV(candidates, uvVersion)
}

func pickUV(candidates []string, versionOf func(string) string) (uv, version string) {
	seen := map[string]bool{}
	for _, p := range candidates {
		if seen[p] || !fileExists(p) {
			continue
		}
		seen[p] = true
		v := versionOf(p)
		if uvAtLeast(v, minUV) {
			return p, v
		}
		if uv == "" {
			uv, version = p, v
		}
	}
	return uv, version
}

var uvRelease = regexp.MustCompile(`^uv (\d+)\.(\d+)`)

// uvAtLeast reports whether a `uv --version` line ("uv 0.11.2 (…)") names version want (major, minor) or newer.
func uvAtLeast(version string, want [2]int) bool {
	m := uvRelease.FindStringSubmatch(version)
	if m == nil {
		return false
	}
	major, _ := strconv.Atoi(m[1])
	minor, _ := strconv.Atoi(m[2])
	return major > want[0] || major == want[0] && minor >= want[1]
}

// useSystemProxy puts a proxy set in the Windows settings into this launcher's environment when the environment
// names none: Go reads only the variables when it fetches uv, and uv and the server inherit them. It must run
// before the first web request, as Go reads the variables once. It returns the proxy used, or "".
func useSystemProxy() string {
	server, override := systemProxy()
	env := proxyEnv(os.Getenv, server, override)
	for _, kv := range env {
		name, value, _ := strings.Cut(kv, "=")
		os.Setenv(name, value)
	}
	if env == nil {
		return ""
	}
	return server
}

// proxyEnv turns the Windows ProxyServer and ProxyOverride settings into proxy variables, or nil when the
// environment already names a proxy or the settings name none for web addresses. ProxyServer is "host:port" for
// every protocol or "http=host:port;https=host:port;…" per protocol.
func proxyEnv(getenv func(string) string, server, override string) []string {
	for _, name := range []string{"HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"} { // Windows names ignore case
		if getenv(name) != "" {
			return nil
		}
	}
	var every, httpProxy, httpsProxy string
	for _, part := range strings.Split(server, ";") {
		scheme, addr, perScheme := strings.Cut(strings.TrimSpace(part), "=")
		switch {
		case !perScheme:
			every = cmp.Or(every, scheme)
		case strings.EqualFold(scheme, "http"):
			httpProxy = addr
		case strings.EqualFold(scheme, "https"):
			httpsProxy = addr
		}
	}
	var env []string
	add := func(name, addr string) {
		if addr != "" && !strings.Contains(addr, "://") {
			addr = "http://" + addr
		}
		if addr != "" {
			env = append(env, name+"="+addr)
		}
	}
	add("HTTPS_PROXY", cmp.Or(httpsProxy, every))
	add("HTTP_PROXY", cmp.Or(httpProxy, every))
	if env == nil {
		return nil
	}
	// This computer is always reached directly: the server and the model server answer on 127.0.0.1. Of
	// ProxyOverride, "*.corp.example" becomes ".corp.example"; "<local>" and "10.*" have no NO_PROXY form.
	direct := []string{"127.0.0.1", "localhost", "::1"}
	if current := getenv("NO_PROXY"); current != "" {
		direct = append(direct, current)
	}
	for _, host := range strings.Split(override, ";") {
		if host = strings.TrimPrefix(strings.TrimSpace(host), "*"); host != "" && !strings.ContainsAny(host, "*<>") {
			direct = append(direct, host)
		}
	}
	return append(env, "NO_PROXY="+strings.Join(direct, ","))
}

func uvAsset() (string, error) {
	arch := map[string]string{"amd64": "x86_64", "arm64": "aarch64"}[runtime.GOARCH]
	if arch == "" {
		return "", fmt.Errorf("no uv build for %s/%s", runtime.GOOS, runtime.GOARCH)
	}
	switch runtime.GOOS {
	case "windows":
		return "uv-" + arch + "-pc-windows-msvc.zip", nil
	case "darwin":
		return "uv-" + arch + "-apple-darwin.tar.gz", nil
	case "linux":
		return "uv-" + arch + "-unknown-linux-musl.tar.gz", nil // static: runs on any distribution
	}
	return "", fmt.Errorf("no uv build for %s", runtime.GOOS)
}

var (
	uvReleases = "https://github.com/astral-sh/uv/releases/latest/download/"
	// uvStall ends a download that has received nothing for this long. There is no limit on the whole download: a
	// slow connection that keeps going finishes.
	uvStall = time.Minute
)

// installUV downloads the uv release for this machine into <home>/bin. Nothing outside that
// folder changes (no shell profile edits, no admin rights).
func installUV(home string, say func(string, ...any)) (string, error) {
	asset, err := uvAsset()
	if err != nil {
		return "", err
	}
	removeStale(filepath.Join(home, "uv-download-*")) // left by a download the launcher quit during
	bin := filepath.Join(home, "bin")
	removeStale(filepath.Join(bin, "*.old-*")) // a uv set aside while it ran (see replaceExecutable)
	url := uvReleases + asset
	say("Downloading uv (one time) from %s", url)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return "", err
	}
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.ResponseHeaderTimeout = uvStall
	resp, err := (&http.Client{Transport: transport}).Do(req)
	if err != nil {
		return "", fmt.Errorf("download failed — check the internet connection (%w)", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("download failed: %s", resp.Status)
	}
	tmp, err := os.CreateTemp(home, "uv-download-*")
	if err != nil {
		return "", err
	}
	defer os.Remove(tmp.Name())
	stalled := time.AfterFunc(uvStall, cancel)
	_, err = io.Copy(tmp, progress{resp.Body, func() { stalled.Reset(uvStall) }})
	stalled.Stop()
	tmp.Close()
	if err != nil {
		if ctx.Err() != nil {
			err = fmt.Errorf("nothing received for %s", uvStall)
		}
		return "", fmt.Errorf("download interrupted: %w", err)
	}

	if err := os.MkdirAll(bin, 0o755); err != nil {
		return "", err
	}
	want := map[string]bool{exeName("uv"): true, exeName("uvx"): true}
	if filepath.Ext(asset) == ".zip" {
		err = unzip(tmp.Name(), bin, want)
	} else {
		err = untar(tmp.Name(), bin, want)
	}
	if err != nil {
		return "", fmt.Errorf("unpacking uv: %w", err)
	}
	uv := filepath.Join(bin, exeName("uv"))
	if !fileExists(uv) {
		return "", fmt.Errorf("uv missing from %s", asset)
	}
	return uv, nil
}

func untar(archive, dest string, want map[string]bool) error {
	f, err := os.Open(archive)
	if err != nil {
		return err
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		return err
	}
	tr := tar.NewReader(gz)
	for {
		h, err := tr.Next()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return err
		}
		if name := path.Base(h.Name); h.Typeflag == tar.TypeReg && want[name] {
			if err := writeExecutable(filepath.Join(dest, name), tr); err != nil {
				return err
			}
		}
	}
}

func unzip(archive, dest string, want map[string]bool) error {
	zr, err := zip.OpenReader(archive)
	if err != nil {
		return err
	}
	defer zr.Close()
	for _, f := range zr.File {
		name := path.Base(f.Name)
		if !want[name] {
			continue
		}
		rc, err := f.Open()
		if err != nil {
			return err
		}
		err = writeExecutable(filepath.Join(dest, name), rc)
		rc.Close()
		if err != nil {
			return err
		}
	}
	return nil
}

// progress calls more each time something arrives.
type progress struct {
	r    io.Reader
	more func()
}

func (p progress) Read(b []byte) (int, error) {
	n, err := p.r.Read(b)
	if n > 0 {
		p.more()
	}
	return n, err
}

// removeStale removes files matching pattern that are more than an hour old (newer ones may be another launcher's
// download in progress; one still in use on Windows stays).
func removeStale(pattern string) {
	found, _ := filepath.Glob(pattern)
	for _, path := range found {
		if st, err := os.Stat(path); err == nil && time.Since(st.ModTime()) > time.Hour {
			_ = os.Remove(path)
		}
	}
}

func writeExecutable(target string, r io.Reader) error {
	out, err := os.CreateTemp(filepath.Dir(target), filepath.Base(target)+".part-*") // another launcher may write one too
	if err != nil {
		return err
	}
	tmp := out.Name()
	_, err = io.Copy(out, r)
	if cerr := out.Close(); err == nil {
		err = cerr
	}
	if err == nil {
		err = os.Chmod(tmp, 0o755)
	}
	if err == nil {
		err = replaceExecutable(tmp, target)
	}
	if err != nil {
		_ = os.Remove(tmp)
	}
	return err
}

var renameFile = os.Rename

// replaceExecutable moves tmp to target. Windows cannot replace a program that is running (an earlier TwinStore may
// still run this uv), but it can rename it: the running one is set aside, to be removed by a later install.
func replaceExecutable(tmp, target string) error {
	err := renameFile(tmp, target)
	if err == nil || !fileExists(target) {
		return err
	}
	aside := fmt.Sprintf("%s.old-%d", target, time.Now().UnixNano())
	if renameFile(target, aside) != nil {
		return err
	}
	if err := renameFile(tmp, target); err != nil {
		_ = renameFile(aside, target)
		return err
	}
	_ = os.Remove(aside) // fails while it runs
	return nil
}
