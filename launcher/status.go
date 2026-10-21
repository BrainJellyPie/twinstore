package main

import (
	"sync"
	"time"
)

// stage is one step on the boot screen.
type stage struct {
	ID     string `json:"id"`
	Label  string `json:"label"`
	State  string `json:"state"` // pending | active | done | error
	Detail string `json:"detail,omitempty"`
}

var stageLabels = [][2]string{
	{"files", "App files"},
	{"uv", "Toolchain (uv)"},
	{"python", "Python & packages"},
	{"ui", "Web interface"},
	{"server", "Simulator"},
}

type status struct {
	mu      sync.Mutex
	stages  []stage
	ready   bool
	err     string
	started time.Time
}

func newStatus() *status {
	s := &status{}
	s.reset()
	return s
}

func (s *status) reset() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.stages = s.stages[:0]
	for _, l := range stageLabels {
		s.stages = append(s.stages, stage{ID: l[0], Label: l[1], State: "pending"})
	}
	s.ready, s.err, s.started = false, "", time.Now()
}

func (s *status) set(id, state, detail string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.stages {
		if s.stages[i].ID == id {
			s.stages[i].State = state
			if detail != "" || state == "done" {
				s.stages[i].Detail = detail
			}
		}
	}
}

func (s *status) activate(id, detail string) { s.set(id, "active", detail) }
func (s *status) done(id, detail string)     { s.set(id, "done", detail) }

func (s *status) fail(id, msg string) {
	s.set(id, "error", "")
	s.mu.Lock()
	s.err, s.ready = msg, false
	s.mu.Unlock()
}

// finish marks every stage done (stages the app skipped, like a prebuilt interface, included).
func (s *status) finish() {
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.stages {
		if s.stages[i].State != "done" {
			s.stages[i].State = "done"
		}
	}
	s.ready = true
}

func (s *status) state(id string) string {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, st := range s.stages {
		if st.ID == id {
			return st.State
		}
	}
	return ""
}

// current is the stage in progress, for blaming an unexpected stop on it.
func (s *status) current() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, st := range s.stages {
		if st.State == "active" {
			return st.ID
		}
	}
	return "server"
}

type statusView struct {
	Stages  []stage  `json:"stages"`
	Ready   bool     `json:"ready"`
	Error   string   `json:"error,omitempty"`
	Elapsed float64  `json:"elapsed"`
	Log     []string `json:"log"`
	Version string   `json:"version"`
	Root    string   `json:"root"`
	Data    string   `json:"data"`
	LogFile string   `json:"log_file"`
}

func (s *status) view() statusView {
	s.mu.Lock()
	defer s.mu.Unlock()
	return statusView{
		Stages: append([]stage(nil), s.stages...), Ready: s.ready, Error: s.err,
		Elapsed: time.Since(s.started).Seconds(), Version: version,
	}
}
