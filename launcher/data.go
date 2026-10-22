package main

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

// dataHome is the folder that holds .data (the stores, their runs, settings, the local model): the per-user folder,
// so a new version, unpacked into a new folder, finds the stores of the one before. A PARASTORE_DATA_HOME the user
// set wins; the server resolves a relative one against its working folder, the app folder.
func (a *app) dataHome() string { return dataHomeOf(a.home, a.root) }

func dataHomeOf(home, root string) string {
	dir := os.Getenv("PARASTORE_DATA_HOME")
	switch {
	case dir == "":
		return home
	case filepath.IsAbs(dir):
		return filepath.Clean(dir)
	}
	return filepath.Join(root, dir)
}

func (a *app) dataFolder() string { return filepath.Join(a.dataHome(), ".data") }

// useClaim takes what claimData found: this launcher uses the data home, or the boot screen says who does.
func (a *app) useClaim(c claim) bool {
	var msg string
	switch {
	case c.unlock != nil:
		a.mu.Lock()
		a.held = c.unlock
		a.mu.Unlock()
		saveInstance(a.dataHome(), a.root, a.url)
		if c.stopped != "" {
			a.log.Printf("Stopped the TwinStore running from %s so this version can use your stores", c.stopped)
		}
		return true
	case c.other != "":
		msg = fmt.Sprintf("Another TwinStore (%s) is still running; quit it and try again.", c.other)
	case c.url != "":
		msg = "This TwinStore is already running at " + c.url + "."
	default:
		msg = "Another TwinStore is starting but does not answer; try again in a moment."
	}
	a.log.Printf("%s", msg)
	a.status.fail("data", msg)
	return false
}

// holdData makes sure this launcher uses the data home before anything touches it: Try again, after another version
// did not quit at first, asks it again.
func (a *app) holdData() bool {
	a.mu.Lock()
	held := a.held != nil
	a.mu.Unlock()
	if held || a.opt.smoke {
		return true
	}
	a.status.activate("data", "Making sure no other TwinStore uses your stores")
	return a.useClaim(claimData(a.home, a.dataHome(), a.root, 20*time.Second))
}

// releaseData lets the next launcher use the data home.
func (a *app) releaseData() {
	a.mu.Lock()
	unlock := a.held
	a.held = nil
	a.mu.Unlock()
	if unlock != nil {
		clearInstance(a.dataHome(), a.url)
		unlock()
	}
}

// pythonEnv is the Python environment, also in the per-user folder, so an update installs only what changed. 0.4.2
// kept environments for long Windows app folder paths in venv\<hash>; uv will not use a folder that holds files but
// is not an environment, so with those there it goes beside them.
func pythonEnv(home string) string {
	dir := filepath.Join(home, "venv")
	if entries, _ := os.ReadDir(dir); len(entries) > 0 && !fileExists(filepath.Join(dir, "pyvenv.cfg")) {
		return filepath.Join(dir, "app")
	}
	return dir
}

// bringStoresOver copies the stores of an earlier version into the per-user data folder, on the first start that
// finds none there: earlier launchers kept them in the app folder (backend/.data), so a new version unpacked into a
// new folder seemed to have lost them. It copies rather than moves, as the earlier version must keep working. When
// none is found the server adds the sample stores itself; a data folder the user chose is left to them.
func (a *app) bringStoresOver() error {
	dest := a.dataFolder()
	if _, err := os.Stat(dest); !errors.Is(err, fs.ErrNotExist) || a.dataHome() != a.home {
		a.status.done("data", "ready")
		return nil
	}
	src, stores := newestStores(a.earlierData())
	if src == "" {
		a.status.done("data", "starting with the sample stores")
		return nil
	}
	from := appFolderOf(src)
	a.status.activate("data", "Bringing your stores over from "+from)
	a.log.Printf("Bringing your stores over from %s", src) // read back by earlierData if this copy is cut short
	st, err := copyData(src, dest)
	if err != nil {
		return fmt.Errorf("from %s: %w", from, err)
	}
	a.log.Printf("Brought %d stores over into %s: %d files copied (%.1f MB), %d hard-linked (%.1f MB), %d left out",
		stores, dest, st.copied, float64(st.copiedBytes)/1e6, st.linked, float64(st.linkedBytes)/1e6, st.skipped)
	a.status.done("data", fmt.Sprintf("%d brought over from %s", stores, from))
	return nil
}

// earlierData lists the data folders earlier launchers used: this app folder's backend/.data (a new version
// unpacked over the old one), then those the last two launcher logs name (log.go keeps the previous run's).
func (a *app) earlierData() []string {
	found := []string{filepath.Join(a.root, "backend", ".data")}
	logs := filepath.Dir(a.log.path)
	for _, name := range []string{"launcher.log", "launcher.prev.log"} {
		found = append(found, loggedData(filepath.Join(logs, name))...)
	}
	return found
}

// Log lines that name a data folder. Every launcher logs "» Starting: uv run --project <app folder>/backend
// --frozen …", its data then being backend/.data; some "» Data folder: <folder>"; this one "» Bringing your stores
// over from <folder>", still there for a copy cut short after the logs have turned over. Arguments are logged
// unquoted, so the project folder is everything up to its "backend" before the next option.
var (
	loggedProject = regexp.MustCompile(`» Starting: uv run --project (.*?([\\/])backend) --`)
	loggedFolder  = regexp.MustCompile(`» (?:Data folder: |Bringing your stores over from )(.+)`)
)

func loggedData(path string) []string {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()
	var found []string
	br := bufio.NewReaderSize(f, 64*1024)
	for {
		line, err := readLine(br, 64*1024)
		if dir := dataNamedIn(line); dir != "" {
			found = append(found, dir)
		}
		if err != nil {
			return found
		}
	}
}

// dataNamedIn returns the data folder a log line names, written with the separator of the system that logged it.
func dataNamedIn(line string) string {
	line = strings.TrimRight(line, "\r ")
	if m := loggedProject.FindStringSubmatch(line); m != nil {
		return m[1] + m[2] + ".data"
	}
	if m := loggedFolder.FindStringSubmatch(line); m != nil {
		return m[1]
	}
	return ""
}

// newestStores returns, of the data folders that hold a store, the one whose stores changed last, and how many
// stores it holds; "" when none does.
func newestStores(dirs []string) (dir string, stores int) {
	var newest time.Time
	seen := map[string]bool{}
	for _, d := range dirs {
		key := filepath.Clean(d)
		if runtime.GOOS == "windows" {
			key = strings.ToLower(key)
		}
		if seen[key] {
			continue
		}
		seen[key] = true
		if n, changed := storesIn(d); n > 0 && (dir == "" || changed.After(newest)) {
			dir, stores, newest = d, n, changed
		}
	}
	return dir, stores
}

// storesIn counts the stores in a data folder (its folders holding metadata.json) and returns when anything in them
// last changed: a run or an edit changes files deep inside, not the folders above.
func storesIn(data string) (n int, changed time.Time) {
	entries, _ := os.ReadDir(data)
	for _, e := range entries {
		store := filepath.Join(data, e.Name())
		if !e.IsDir() || !fileExists(filepath.Join(store, "metadata.json")) {
			continue
		}
		n++
		_ = filepath.WalkDir(store, func(_ string, d fs.DirEntry, err error) error {
			if err == nil {
				if info, err := d.Info(); err == nil && info.ModTime().After(changed) {
					changed = info.ModTime()
				}
			}
			return nil
		})
	}
	return n, changed
}

// appFolderOf names a data folder by the app folder it is in (…/app for …/app/backend/.data), as the user knows it.
func appFolderOf(data string) string {
	if backend := filepath.Dir(data); filepath.Base(data) == ".data" && filepath.Base(backend) == "backend" {
		return filepath.Dir(backend)
	}
	return data
}

// Files from linkFrom up (the local model, hundreds of MB to GBs) are hard-linked when the earlier folder is on the
// same volume: no time, no space. Such files are only ever replaced whole, so neither version changes the other's;
// smaller ones are copied, and so is a large one that cannot be linked (another volume, a file system without links).
var (
	linkFrom = int64(64 << 20)
	linkFile = os.Link
)

type copyStats struct {
	copied, linked, skipped  int
	copiedBytes, linkedBytes int64
}

// copyData copies the data folder src to dest through dest.migrating, renamed into place once complete: a copy cut
// short (the launcher quit, the computer turned off) is made again at the next start, never used half done.
func copyData(src, dest string) (copyStats, error) {
	if resolved, err := filepath.EvalSymlinks(src); err == nil {
		src = resolved // the walk would not enter a linked folder
	}
	part := dest + ".migrating"
	if err := os.RemoveAll(part); err != nil {
		return copyStats{}, err
	}
	st, err := copyTree(src, part)
	if err == nil {
		err = renameDir(part, dest)
	}
	if err != nil {
		_ = os.RemoveAll(part)
	}
	return st, err
}

func copyTree(src, dst string) (copyStats, error) {
	var st copyStats
	err := filepath.WalkDir(src, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}
		if leftOut(rel, d) {
			st.skipped++
			if d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		info, err := d.Info()
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		switch {
		case d.IsDir():
			return os.MkdirAll(target, info.Mode().Perm()|0o700)
		case info.Size() >= linkFrom && linkFile(path, target) == nil:
			st.linked++
			st.linkedBytes += info.Size()
			return nil
		}
		st.copied++
		st.copiedBytes += info.Size()
		return copyFile(path, target, info)
	})
	return st, err
}

// leftOut is what the copy skips: the llama.cpp runtime (this version fetches its own), downloads cut short (*.part),
// files caught mid-write (*.tmp-*) and anything that is not a plain file or folder.
func leftOut(rel string, d fs.DirEntry) bool {
	if d.IsDir() {
		return filepath.ToSlash(rel) == "local_vlm/bin"
	}
	name := d.Name()
	return !d.Type().IsRegular() || strings.HasSuffix(name, ".part") || strings.Contains(name, ".tmp-")
}

// copyFile keeps the file's permissions (settings/providers.json holds API keys, readable by its owner only) and
// modification time, and has it on disk before the folder is renamed into place: after a power cut the rename could
// otherwise survive files left empty, and the copy would not be made again.
func copyFile(src, dst string, info fs.FileInfo) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.OpenFile(dst, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, info.Mode().Perm()|0o600)
	if err != nil {
		return err
	}
	_, err = io.Copy(out, in)
	if err == nil {
		err = out.Sync()
	}
	if cerr := out.Close(); err == nil {
		err = cerr
	}
	if err != nil {
		return err
	}
	return os.Chtimes(dst, info.ModTime(), info.ModTime())
}

// renameDir renames a folder just written. On Windows the antivirus opens new files for a moment to scan them, and a
// folder holding an open file cannot be renamed, so it is tried again for a while.
func renameDir(from, to string) error {
	var err error
	for range 40 {
		if err = os.Rename(from, to); err == nil || runtime.GOOS != "windows" {
			return err
		}
		time.Sleep(250 * time.Millisecond)
	}
	return err
}
