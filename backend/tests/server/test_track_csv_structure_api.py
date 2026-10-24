import pytest

from tests.server.test_movement_api import CSV, URL, client
from tests.engine.test_track_csv_structure import sparse_tracks


@pytest.mark.parametrize("row", ["t,0,0,1,250", "t,0,0,10,", 't,0,0,"10', "t\0suffix,0,0,10"])
def test_structural_track_error_keeps_previous_report(client, row):
    original = client.post(URL, files={"file": ("tracks.csv", CSV, "text/csv")}).json()
    data = ("track_id,x,y,timestamp_sec\n" + row + "\n").encode()
    response = client.post(URL, files={"file": ("tracks.csv", data, "text/csv")})
    assert response.status_code == 400 and "CSV" in response.text
    assert client.get(URL).json() == original


def test_sparse_track_table_is_rejected_without_replacing_previous_report(client):
    original = client.post(URL, files={"file": ("tracks.csv", CSV, "text/csv")}).json()
    response = client.post(URL, files={"file": ("tracks.csv", sparse_tracks(), "text/csv")})
    assert response.status_code == 400 and "cells" in response.text
    assert client.get(URL).json() == original
