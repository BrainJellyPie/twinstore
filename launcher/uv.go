package main

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"runtime"
	"time"
)

// findUV returns a uv already on this machine: on PATH, in the standard install folders, or
// the copy the launcher fetched earlier.
func findUV(home string) string {
	if p, err := exec.LookPath("uv"); err == nil {
		return p
	}
	user, _ := os.UserHomeDir()
	for _, dir := range []string{filepath.Join(home, "bin"), filepath.Join(user, ".local", "bin"), filepath.Join(user, ".cargo", "bin")} {
		if p := filepath.Join(dir, exeName("uv")); fileExists(p) {
			return p
		}
	}
	return ""
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

// installUV downloads the uv release for this machine into <home>/bin. Nothing outside that
// folder changes (no shell profile edits, no admin rights).
func installUV(home string, say func(string, ...any)) (string, error) {
	asset, err := uvAsset()
	if err != nil {
		return "", err
	}
	url := "https://github.com/astral-sh/uv/releases/latest/download/" + asset
	say("Downloading uv (one time) from %s", url)
	client := http.Client{Timeout: 5 * time.Minute}
	resp, err := client.Get(url)
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
	if _, err := io.Copy(tmp, resp.Body); err != nil {
		tmp.Close()
		return "", fmt.Errorf("download interrupted: %w", err)
	}
	tmp.Close()

	bin := filepath.Join(home, "bin")
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

func writeExecutable(target string, r io.Reader) error {
	tmp := target + ".part"
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o755)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, r); err != nil {
		out.Close()
		return err
	}
	if err := out.Close(); err != nil {
		return err
	}
	return os.Rename(tmp, target)
}
