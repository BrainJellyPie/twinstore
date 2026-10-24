"""Accepted shopper labels must survive retained paired evidence and its exports."""

import csv
import io

import pytest

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import personas_path
from tests.server.test_factorial_api import PID, client, start_fixture


@pytest.mark.parametrize("prefix", [
    "plain", "고객", "customer A", " customer ", "customer 😀", "x" * 512,
    "p~s1", "p~t1-12h-linked-cafe-20s", "a/b", "a\\b", "../outside",
    "cliente-é", "cliente-e\u0301", "001", "NULL", "=SUM(1,2)", "@customer", 'line,one\n"two"',
])
def test_accepted_customer_identifiers_retain_exact_paired_evidence(client, monkeypatch, prefix):
    people = read_json(personas_path(PID))[:40]
    ids = [f"{prefix}-{index}" for index in range(len(people))]
    for person, identifier in zip(people, ids, strict=True):
        person.update(id=identifier, day=1, arrival_hour=12)
    write_json(personas_path(PID), people)

    _, root, request = start_fixture(client, monkeypatch)
    response = client.post(root + "/preview", json=request)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["complete_panel"] == len(ids) == 40
    assert {row["persona_id"] for row in report["rows"]} == set(ids)
    assert [contrast["estimate"] for contrast in report["contrasts"]] == [5.5, 6.5, 7]
    exported = client.post(root + "/export.csv", json=request)
    assert exported.status_code == 200, exported.text
    rows = list(csv.reader(io.StringIO(exported.text, newline="")))
    start = rows.index(["persona_id", "complete", "00", "10", "01", "11"]) + 1
    expected = {"'" + identifier if identifier.lstrip().startswith(("=", "+", "-", "@", "'")) else identifier
                for identifier in ids}
    assert {row[0] for row in rows[start:]} == expected
