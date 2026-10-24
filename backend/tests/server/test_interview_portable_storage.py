"""Exercise shopper storage under case-insensitive and Windows-name constraints.

The adapter models filename lookup only; it is not a native Windows filesystem test.
The actual interview service, JSON persistence and fake-model lifecycle still run.
"""

import ntpath
from pathlib import Path

import pytest

from store_emulator.application import interview
from store_emulator.application.storage import io
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.interview import Interview, InterviewMessage, InterviewQuestion
from tests.server.test_interview_customer_identifiers import saved_run


@pytest.fixture
def portable_names(monkeypatch):
    original_exists, original_unlink = Path.exists, Path.unlink
    original_read, original_write = io.read_text, interview.write_json

    def lookup(path):
        # All transcript files in this fixture are written through the adapter.
        return path.with_name(path.name.lower()) if "interviews" in path.parts else path

    def write(path, data):
        if "interviews" in path.parts and ntpath.isreserved(path.name):
            raise OSError(f"Reserved Windows filename: {path.name}")
        original_write(lookup(path), data)

    monkeypatch.setattr(Path, "exists", lambda path: original_exists(lookup(path)))
    monkeypatch.setattr(Path, "unlink", lambda path, **kw: original_unlink(lookup(path), **kw))
    monkeypatch.setattr(io, "read_text", lambda path: original_read(lookup(path)))
    monkeypatch.setattr(interview, "write_json", write)


@pytest.mark.parametrize("ids", [
    ["CustomerA", "customera"], ["M1001", "m1001", "M1002"],
    ["CON", "con"], ["NUL", "AUX"], ["PRN", "COM1", "LPT9"],
])
def test_distinct_shoppers_keep_separate_conversations(saved_run, portable_names, ids):
    saved_run(ids)
    for sid in ids:
        transcript = interview.interview("project", "run", sid, InterviewQuestion(question=f"Question for {sid}?"), SimulationConfig())
        assert transcript.persona_id == sid
        assert len(transcript.messages) == 2
    for sid in ids:
        transcript = interview.get_interview("project", "run", sid)
        assert transcript.persona_id == sid
        assert transcript.messages[0].text == f"Question for {sid}?"
    interview.clear_interview("project", "run", ids[0])
    assert interview.get_interview("project", "run", ids[0]).messages == []
    for sid in ids[1:]:
        assert len(interview.get_interview("project", "run", sid).messages) == 2


@pytest.mark.parametrize("first", ["CustomerA", "customera"])
def test_legacy_transcript_belongs_only_to_its_exact_customer(saved_run, portable_names, first):
    other = "customera" if first == "CustomerA" else "CustomerA"
    base = saved_run([first, other])
    legacy = Interview(run_id="run", persona_id=first, messages=[InterviewMessage(role="shopper", text="Existing answer")])
    interview.write_json(base / "interviews" / f"{first}.json", legacy.model_dump(mode="json"))
    assert interview.get_interview("project", "run", first) == legacy
    assert interview.get_interview("project", "run", other).messages == []
    interview.clear_interview("project", "run", other)
    assert interview.get_interview("project", "run", first) == legacy
    updated = interview.interview("project", "run", first, InterviewQuestion(question="Next question?"), SimulationConfig())
    assert len(updated.messages) == 3
    assert interview.get_interview("project", "run", first) == updated
    interview.clear_interview("project", "run", first)
    assert interview.get_interview("project", "run", first).messages == []


def test_damaged_current_transcript_can_still_be_reset(saved_run, portable_names):
    base = saved_run(["CustomerA", "customera"])
    for sid in ["CustomerA", "customera"]:
        interview.interview("project", "run", sid, InterviewQuestion(question=f"Question for {sid}?"), SimulationConfig())
    # Damage only the file containing CustomerA, leaving the other conversation intact.
    for path in (base / "interviews").rglob("*.json"):
        if io.read_json(path)["persona_id"] == "CustomerA":
            path.write_text('{"persona_id":', encoding="utf-8")
    interview.clear_interview("project", "run", "CustomerA")
    assert interview.get_interview("project", "run", "CustomerA").messages == []
    assert len(interview.get_interview("project", "run", "customera").messages) == 2


def test_damaged_legacy_record_can_be_reset_without_erasing_unknown_owner(saved_run, portable_names):
    base = saved_run(["CustomerA", "customera"])
    legacy = base / "interviews/customera.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"persona_id":', encoding="utf-8")
    interview.clear_interview("project", "run", "CustomerA")
    assert interview.get_interview("project", "run", "CustomerA").messages == []
    assert legacy.read_text(encoding="utf-8") == '{"persona_id":'
    reply = interview.interview("project", "run", "CustomerA", InterviewQuestion(question="Start over?"), SimulationConfig())
    assert len(reply.messages) == 2
