//go:build windows

package main

import (
	"os/exec"
	"strconv"
	"syscall"
	"unsafe"
)

const createNoWindow = 0x08000000

// setupProcess starts console programs (uv, Python, Node) without a console window.
func setupProcess(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: createNoWindow | syscall.CREATE_NEW_PROCESS_GROUP, HideWindow: true}
}

func killTree(cmd *exec.Cmd) {
	if cmd.Process == nil {
		return
	}
	kill := exec.Command("taskkill", "/T", "/F", "/PID", strconv.Itoa(cmd.Process.Pid))
	setupProcess(kill)
	_ = kill.Run()
}

// killGroup has nothing to do on Windows: the server ties llama-server to itself with a job object, which ends it
// when the server ends.
func killGroup(*exec.Cmd) {}

const errSharingViolation syscall.Errno = 32 // ERROR_SHARING_VIOLATION

// tryLock opens path without sharing it, which keeps every other open out until this launcher ends, however it
// ends. busy: another launcher has it open. When the file cannot be opened otherwise, unlock does nothing, as
// before the lock.
func tryLock(path string) (unlock func(), busy bool) {
	name, err := syscall.UTF16PtrFromString(path)
	if err != nil {
		return func() {}, false
	}
	h, err := syscall.CreateFile(name, syscall.GENERIC_READ|syscall.GENERIC_WRITE, 0, nil, syscall.OPEN_ALWAYS,
		syscall.FILE_ATTRIBUTE_NORMAL, 0)
	if err != nil {
		return func() {}, err == errSharingViolation
	}
	return func() { syscall.CloseHandle(h) }, false
}

// systemProxy reads the proxy set in the Windows settings (Settings › Network › Proxy, or Internet Options):
// ProxyServer while ProxyEnable is on, and its ProxyOverride bypass list. A setup script (PAC) is not read.
func systemProxy() (server, override string) {
	var key syscall.Handle
	path, _ := syscall.UTF16PtrFromString(`Software\Microsoft\Windows\CurrentVersion\Internet Settings`)
	if syscall.RegOpenKeyEx(syscall.HKEY_CURRENT_USER, path, 0, syscall.KEY_READ, &key) != nil {
		return "", ""
	}
	defer syscall.RegCloseKey(key)
	var enabled, kind uint32
	size := uint32(unsafe.Sizeof(enabled))
	name, _ := syscall.UTF16PtrFromString("ProxyEnable")
	if syscall.RegQueryValueEx(key, name, nil, &kind, (*byte)(unsafe.Pointer(&enabled)), &size) != nil ||
		kind != syscall.REG_DWORD || enabled == 0 {
		return "", ""
	}
	return regString(key, "ProxyServer"), regString(key, "ProxyOverride")
}

func regString(key syscall.Handle, value string) string {
	name, _ := syscall.UTF16PtrFromString(value)
	var kind, size uint32
	if syscall.RegQueryValueEx(key, name, nil, &kind, nil, &size) != nil || kind != syscall.REG_SZ || size < 2 {
		return ""
	}
	buf := make([]uint16, size/2+1) // +1: a stored string may lack its terminating NUL
	size = uint32(len(buf) * 2)
	if syscall.RegQueryValueEx(key, name, nil, &kind, (*byte)(unsafe.Pointer(&buf[0])), &size) != nil {
		return ""
	}
	return syscall.UTF16ToString(buf)
}

func openBrowser(url string) {
	cmd := exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	setupProcess(cmd)
	_ = cmd.Start()
}

func detachFromBundle() bool { return false }
