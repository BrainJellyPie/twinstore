import json
from itertools import permutations

import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.shelf_lab.levers import LeverOutcome, summarize_levers


def outcome(name, *, kind="price", valid=True, before=0.25, after=0.75):
    return LeverOutcome(id=name, kind=kind, target_sku_before="tea", target_sku_after="tea",
                        personas=4 if valid else 0, picked_before=before if valid else 0,
                        picked_after=after if valid else 0, changed_pick=0.5 if valid else 0,
                        errors=0 if valid else 4, answers_before=[], answers_after=[])


@pytest.mark.parametrize("missing", [1, 2, 9, 50])
@pytest.mark.parametrize("seed", [0, 19, -7])
def test_failed_comparisons_do_not_dilute_measured_effect_or_interval(missing, seed):
    good = [outcome("a"), outcome("b", before=0.5, after=0.5)]
    expected = summarize_levers(good, seed=seed, n_boot=120)
    actual = summarize_levers(good + [outcome(str(i), valid=False) for i in range(missing)], seed=seed, n_boot=120)
    assert actual == expected
    assert actual[0].counterfactuals == 2 and actual[0].delta_picked == 0.25


@pytest.mark.parametrize("order", list(permutations(range(3))))
def test_failed_only_kinds_do_not_report_a_zero_effect(order):
    cases = [outcome("ok"), outcome("bad", valid=False), outcome("remove-bad", kind="remove", valid=False)]
    summaries = summarize_levers([cases[i] for i in order], n_boot=100)
    assert [(s.kind, s.counterfactuals, s.delta_picked, s.changed_pick) for s in summaries] == [("price", 1, 0.5, 0.5)]


@pytest.mark.parametrize("cases", [[], [outcome("bad", valid=False)],
                                   [outcome("bad", valid=False), outcome("bad2", kind="remove", valid=False)]])
def test_no_valid_pairs_produce_no_summary(cases):
    assert summarize_levers(cases) == []


def test_genuine_zero_effect_remains_a_valid_observation():
    summary = summarize_levers([outcome("zero", before=0.0, after=0.0)])[0]
    assert summary.counterfactuals == 1 and summary.delta_picked == summary.ci_low == summary.ci_high == 0


@pytest.mark.parametrize("valid", [[], [False], [False, False], [True, False], [True]])
def test_cli_marks_missing_evidence_and_fails_only_when_no_comparison_is_usable(tmp_path, monkeypatch, capsys, valid):
    from store_emulator import lab_cli

    cases = [outcome(f"cf{i}", valid=ok) for i, ok in enumerate(valid)]
    monkeypatch.setattr(lab_cli, "local_config", lambda: None)
    monkeypatch.setattr(lab_cli, "capture_llm_config", lambda *args: LLMConfig(model="offline"))
    monkeypatch.setattr(lab_cli, "LiteLLMClient", lambda *args: None)
    monkeypatch.setattr(lab_cli, "load_counterfactuals", lambda *args, **kwargs: cases)

    async def run(_llm, cf, *args, **kwargs):
        return cf

    monkeypatch.setattr(lab_cli, "run_lever", run)
    people = tmp_path / "personas.json"
    people.write_text("[]")
    output = tmp_path / "out.jsonl"
    code = lab_cli.main(["levers", "--bench", str(tmp_path), "--personas-file", str(people), "--out", str(output)])
    captured = capsys.readouterr()
    assert code == (0 if any(valid) else 1)
    assert [json.loads(line)["id"] for line in output.read_text().splitlines()] == [case.id for case in cases]
    if False in valid:
        assert "unavailable" in captured.err.lower()
        assert "0.00 → 0.00" not in captured.err
    if not any(valid):
        assert "no valid" in captured.err.lower()
        assert "price" not in captured.out
