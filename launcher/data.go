package main

import (
	"bufio"
	"cmp"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"slices"
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
	return a.useClaim(claimData(a.home, a.dataHome(), a.root, claimWait))
}

// holdForSmoke keeps the data home --smoke took (nil when another launcher holds it) until releaseData.
func (a *app) holdForSmoke(unlock func()) {
	a.mu.Lock()
	a.held = unlock
	a.mu.Unlock()
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
// is not an environment, so with those there it goes beside them. A data folder the user chose gets an environment of
// its own (venv-<hash>): the lock is per data folder, so a launcher on it may run beside one on the per-user folder,
// and two versions syncing one environment would change it under each other's running server.
func pythonEnv(home, data string) string {
	if data != home {
		sum := sha256.Sum256([]byte(folderKey(data)))
		return filepath.Join(home, "venv-"+hex.EncodeToString(sum[:4]))
	}
	dir := filepath.Join(home, "venv")
	if entries, _ := os.ReadDir(dir); len(entries) > 0 && !fileExists(filepath.Join(dir, "pyvenv.cfg")) {
		return filepath.Join(dir, "app")
	}
	return dir
}

// folderKey is a folder as the file system compares it: Windows ignores case.
func folderKey(dir string) string {
	key := filepath.Clean(dir)
	if runtime.GOOS == "windows" {
		key = strings.ToLower(key)
	}
	return key
}

// bringStoresOver copies the stores of an earlier version into the per-user data folder, on the first start that
// finds none there: earlier launchers kept them in the app folder (backend/.data), so a new version unpacked into a
// new folder seemed to have lost them. It copies rather than moves, as the earlier version must keep working. When
// none is found the server adds the sample stores itself; a data folder the user chose is left to them. A folder that
// may hold stores but cannot be read stops the start (the sample stores would otherwise take their place for good),
// and so does a copy that fails, until the user chooses to start without them.
func (a *app) bringStoresOver() error {
	dest := a.dataFolder()
	if _, err := os.Stat(dest); !errors.Is(err, fs.ErrNotExist) || a.dataHome() != a.home {
		if a.dataHome() == a.home {
			forgetEarlierData(a.home)
		}
		a.status.done("data", "ready")
		return nil
	}
	if a.skipData.Load() {
		a.log.Printf("Starting without bringing your stores over, as chosen; they stay where they are")
		a.status.done("data", "started without them")
		return nil
	}
	src, stores, err := newestStores(a.earlierData())
	if err != nil {
		return err
	}
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
	forgetEarlierData(a.home)
	a.log.Printf("Brought %d stores over into %s: %d files copied (%.1f MB), %d hard-linked (%.1f MB), %d left out, "+
		"%d could not be read", stores, dest, st.copied, float64(st.copiedBytes)/1e6, st.linked,
		float64(st.linkedBytes)/1e6, st.skipped, len(st.unreadable))
	for i, problem := range st.unreadable {
		if i == 50 {
			a.log.Printf("… and %d more", len(st.unreadable)-i)
			break
		}
		a.log.Printf("Could not read %s", problem)
	}
	detail := fmt.Sprintf("%d brought over from %s", stores, from)
	if n := len(st.unreadable); n > 0 {
		detail += fmt.Sprintf("; %d files could not be read (see the log)", n)
	}
	a.status.done("data", detail)
	return nil
}

// earlierDataNote holds the data folders earlier launchers' logs named, noted before a log turned over.
func earlierDataNote(home string) string { return filepath.Join(home, "earlier-data.json") }

// rememberEarlierData notes the data folders the logs name, before this launcher's log turns them over. Until the
// per-user data folder exists the note keeps them, however often the logs turn over before the stores are brought
// over (a start quit early, or one on a data folder of the user's choosing).
func rememberEarlierData(home string) {
	note := earlierDataNote(home)
	if _, err := os.Stat(filepath.Join(home, ".data")); !errors.Is(err, fs.ErrNotExist) {
		forgetEarlierData(home)
		return
	}
	known := notedEarlierData(note)
	all := uniqueFolders(append(slices.Clone(known), loggedDataIn(filepath.Join(home, "logs"))...))
	if len(all) > 64 {
		all = all[len(all)-64:]
	}
	if slices.Equal(all, known) {
		return
	}
	raw, _ := json.Marshal(all)
	tmp := fmt.Sprintf("%s.%d.tmp", note, os.Getpid())
	if os.WriteFile(tmp, raw, 0o644) != nil || os.Rename(tmp, note) != nil {
		_ = os.Remove(tmp)
	}
}

func forgetEarlierData(home string) { _ = os.Remove(earlierDataNote(home)) }

func notedEarlierData(note string) []string {
	raw, err := os.ReadFile(note)
	if err != nil {
		return nil
	}
	var dirs []string
	if json.Unmarshal(raw, &dirs) != nil {
		return nil
	}
	return dirs
}

func uniqueFolders(dirs []string) []string {
	seen := map[string]bool{}
	var unique []string
	for _, d := range dirs {
		if key := folderKey(d); d != "" && !seen[key] {
			seen[key] = true
			unique = append(unique, d)
		}
	}
	return unique
}

// earlierData lists the data folders earlier launchers used: this app folder's backend/.data (a new version
// unpacked over the old one), then those noted from the logs before they turned over, then those the logs name now.
func (a *app) earlierData() []string {
	found := []string{filepath.Join(a.root, "backend", ".data")}
	found = append(found, notedEarlierData(earlierDataNote(a.home))...)
	return append(found, loggedDataIn(filepath.Join(a.home, "logs"))...)
}

// loggedDataIn returns the data folders the launcher logs in dir name.
func loggedDataIn(dir string) []string {
	logs, _ := filepath.Glob(filepath.Join(dir, "launcher*.log"))
	slices.Sort(logs)
	var found []string
	for _, log := range logs {
		found = append(found, loggedData(log)...)
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
// stores it holds; "" when none does. A folder that is there but cannot be read may hold the newest stores: with no
// other to bring over, it is an error rather than a start with the sample stores.
func newestStores(dirs []string) (dir string, stores int, err error) {
	var newest time.Time
	var unreadable error
	for _, d := range uniqueFolders(dirs) {
		n, changed, err := storesIn(d)
		if err != nil {
			unreadable = cmp.Or(unreadable, fmt.Errorf("from %s (it cannot be read): %w", appFolderOf(d), err))
			continue
		}
		if n > 0 && (dir == "" || changed.After(newest)) {
			dir, stores, newest = d, n, changed
		}
	}
	if dir == "" {
		return "", 0, unreadable
	}
	return dir, stores, nil
}

// storesIn counts the stores in a data folder (its folders, or links to folders, holding metadata.json) and returns
// when anything in them last changed: a run or an edit changes files deep inside, not the folders above. A folder
// that is not there holds none.
func storesIn(data string) (n int, changed time.Time, err error) {
	if st, err := os.Stat(data); err != nil || !st.IsDir() {
		if err == nil || errors.Is(err, fs.ErrNotExist) {
			err = nil
		}
		return 0, changed, err
	}
	entries, err := os.ReadDir(data)
	if err != nil {
		return 0, changed, err
	}
	for _, e := range entries {
		store := filepath.Join(data, e.Name())
		if !fileExists(filepath.Join(store, "metadata.json")) { // follows a link to a store moved elsewhere
			continue
		}
		n++
		if resolved, err := filepath.EvalSymlinks(store); err == nil {
			store = resolved
		}
		_ = filepath.WalkDir(store, func(_ string, d fs.DirEntry, err error) error {
			if err == nil {
				if info, err := d.Info(); err == nil && info.ModTime().After(changed) {
					changed = info.ModTime()
				}
			}
			return nil
		})
	}
	return n, changed, nil
}

// appFolderOf names a data folder by the app folder it is in (…/app for …/app/backend/.data), as the user knows it.
func appFolderOf(data string) string {
	if backend := filepath.Dir(data); filepath.Base(data) == ".data" && filepath.Base(backend) == "backend" {
		return filepath.Dir(backend)
	}
	return data
}

// Files from linkFrom up in local_vlm (the local model, hundreds of MB to GBs) are hard-linked when the earlier folder
// is on the same volume: no time, no space. The model files are only ever replaced whole, so neither version changes
// the other's; everything else is copied (a store's files may be rewritten in place), and so is a model file that
// cannot be linked (another volume, a file system without links).
var (
	linkFrom   = int64(64 << 20)
	linkFile   = os.Link
	openSource = os.Open
)

type copyStats struct {
	copied, linked, skipped  int
	copiedBytes, linkedBytes int64
	unreadable               []string // files (and folders) that could not be read, left out: "<path>: <error>"
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
	c := copier{entered: map[string]bool{folderKey(src): true}}
	err := c.tree(src, part, "")
	if err == nil {
		err = renameDir(part, dest)
	}
	if err != nil {
		_ = os.RemoveAll(part)
	}
	return c.st, err
}

type copier struct {
	st      copyStats
	entered map[string]bool // folders walked, so a link to a folder above is not followed round
}

// readError is a failure to read the earlier folder, as opposed to one writing the copy (a full disk).
type readError struct{ err error }

func (e readError) Error() string { return e.err.Error() }
func (e readError) Unwrap() error { return e.err }

// tree copies src to dst; rel is src's place in the data folder being copied. A file that cannot be read is left out
// and reported, unless it is a store's metadata.json (without it the store is not there at all); the stores' own
// folders and the data folder must be readable. Links are followed: a store moved to another disk and linked back.
func (c *copier) tree(src, dst, rel string) error {
	return filepath.WalkDir(src, func(path string, d fs.DirEntry, err error) error {
		inner, rerr := filepath.Rel(src, path)
		if rerr != nil {
			return rerr
		}
		sub := filepath.Join(rel, inner) // its place in the data folder
		if err != nil {
			if !optional(sub, true) {
				return err
			}
			c.unreadable(sub, err)
			if d != nil && d.IsDir() {
				return filepath.SkipDir
			}
			return nil
		}
		return c.entry(path, filepath.Join(dst, inner), sub, d)
	})
}

func splitRel(rel string) []string {
	if rel == "" || rel == "." {
		return nil
	}
	return strings.Split(rel, string(filepath.Separator))
}

func (c *copier) entry(path, target, rel string, d fs.DirEntry) error {
	if leftOut(rel, d) {
		c.st.skipped++
		if d.IsDir() {
			return filepath.SkipDir
		}
		return nil
	}
	if d.Type()&fs.ModeSymlink != 0 {
		return c.link(path, target, rel)
	}
	info, err := d.Info()
	if err != nil { // gone since the folder was read (the earlier version still runs)
		return c.unreadableOr(rel, d.IsDir(), err)
	}
	if d.IsDir() {
		return os.MkdirAll(target, info.Mode().Perm()|0o700)
	}
	return c.file(path, target, rel, info)
}

// link copies what a link points to, a file or a folder; a link to nothing is left out.
func (c *copier) link(path, target, rel string) error {
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		c.st.skipped++
		return nil
	}
	info, err := os.Stat(resolved)
	if err != nil {
		return c.unreadableOr(rel, false, err)
	}
	if !info.IsDir() {
		if !info.Mode().IsRegular() {
			c.st.skipped++
			return nil
		}
		return c.file(resolved, target, rel, info)
	}
	key := folderKey(resolved)
	if c.entered[key] {
		c.st.skipped++
		return nil
	}
	c.entered[key] = true
	return c.tree(resolved, target, rel)
}

func (c *copier) file(path, target, rel string, info fs.FileInfo) error {
	if info.Size() >= linkFrom && strings.HasPrefix(filepath.ToSlash(rel), "local_vlm/") && linkFile(path, target) == nil {
		c.st.linked++
		c.st.linkedBytes += info.Size()
		return nil
	}
	if err := copyFile(path, target, info); err != nil {
		var unreadable readError
		if !errors.As(err, &unreadable) {
			return err
		}
		_ = os.Remove(target)
		return c.unreadableOr(rel, false, unreadable.err)
	}
	c.st.copied++
	c.st.copiedBytes += info.Size()
	return nil
}

func (c *copier) unreadableOr(rel string, dir bool, err error) error {
	if !optional(rel, dir) {
		return err
	}
	c.unreadable(rel, err)
	return nil
}

func (c *copier) unreadable(rel string, err error) {
	c.st.unreadable = append(c.st.unreadable, fmt.Sprintf("%s: %v", filepath.ToSlash(rel), err))
}

// optional reports whether the copy goes on without rel when it cannot be read: not the data folder itself, a
// store's folder (directly in it) or any metadata.json.
func optional(rel string, dir bool) bool {
	parts := splitRel(rel)
	switch {
	case len(parts) == 0:
		return false
	case dir && len(parts) == 1:
		return false
	}
	return filepath.Base(rel) != "metadata.json"
}

// leftOut is what the copy skips: downloads cut short (*.part), files caught mid-write (*.tmp-*) and devices, pipes
// and sockets. Other files Windows marks as special, such as files OneDrive keeps in the cloud (Go reports them as
// irregular), are read like any file. The llama.cpp runtime (local_vlm/bin) comes along with the model: the app
// starts a local model the user already has without asking, but never downloads one unasked, so a model brought
// over without its runtime would not start.
func leftOut(rel string, d fs.DirEntry) bool {
	if d.IsDir() {
		return false
	}
	name := d.Name()
	return d.Type()&(fs.ModeDevice|fs.ModeCharDevice|fs.ModeNamedPipe|fs.ModeSocket) != 0 ||
		strings.HasSuffix(name, ".part") || strings.Contains(name, ".tmp-")
}

// copyFile keeps the file's permissions (settings/providers.json holds API keys, readable by its owner only) and
// modification time, and has it on disk before the folder is renamed into place: after a power cut the rename could
// otherwise survive files left empty, and the copy would not be made again.
func copyFile(src, dst string, info fs.FileInfo) error {
	in, err := openSource(src)
	if err != nil {
		return readError{err}
	}
	defer in.Close()
	out, err := os.OpenFile(dst, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, info.Mode().Perm()|0o600)
	if err != nil {
		return err
	}
	_, err = io.Copy(out, sourceReader{in})
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

// sourceReader tells a failure reading the earlier folder from one writing the copy.
type sourceReader struct{ r io.Reader }

func (s sourceReader) Read(p []byte) (int, error) {
	n, err := s.r.Read(p)
	if err != nil && err != io.EOF {
		err = readError{err}
	}
	return n, err
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
