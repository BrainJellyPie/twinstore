"""Exact venue-removal effects without recalculating every whole-town report."""

import math
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from store_emulator.domain.town import Building, Town, TownArchetype, TownSpec, Venue, VenueCategory
from store_emulator.engine.town import demand
from store_emulator.engine.town.generator import generate_town


def test_synergy_reuses_the_demand_calculation(monkeypatch):
    town = generate_town(TownSpec(size_m=200, venue_density=4, seed=24102490))
    calls = []
    original = demand.estimate_demand

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(demand, "estimate_demand", counted)
    rows = demand.synergy_analysis(town)
    assert len(rows) == len(town.venues) - 1
    assert len(calls) <= 2, "Each venue removal reran all origin/category demand calculations"


@pytest.mark.parametrize("case", range(12))
def test_shared_calculation_matches_explicit_venue_removal(case):
    hours = [[], [0, 8, 12, 18, 23], list(range(24))][case % 3]
    day_type = ["weekday", "weekend", "holiday"][case // 3 % 3]
    focal = Venue(id="focal", name="Focal", category="cafe" if case % 2 else "convenience",
                  x=100, y=100, open_hour=7 if case % 2 else 0, close_hour=22 if case % 2 else 24)
    venues = [focal]
    for index, category in enumerate(VenueCategory):
        for k in range(2):
            start, end = [(0, 24), (22, 6), (8, 18), (7, 7)][(index + k + case) % 4]
            venues.append(Venue(id=f"v{index}-{k}", name=f"{category} {k}", category=category,
                                x=100 + (index - 5) * 13, y=100 + k * 80,
                                attractiveness=0.2 + (index % 5) * 0.7, open_hour=start, close_hour=end))
    town = Town(id="t", name="Mixed boundaries", archetype=TownArchetype.MIXED, size_m=400,
                focal_venue_id="focal", venues=venues, buildings=[] if case == 11 else [
                    Building(id="a", kind="apartment", x=90, y=80, residents=300, workers=20),
                    Building(id="s", kind="school", x=200, y=150, students=400, workers=30),
                    Building(id="h", kind="hotel", x=20, y=170, visitors=200, workers=40),
                ])
    params = demand.DemandParams()
    if case % 2:
        params.alpha = 1.3
        params.outside_option_m = 150
        params.substitutes = {**params.substitutes, VenueCategory.CAFE: 0.35, VenueCategory.BAR: 0.1}
    kwargs = dict(day_type=day_type, hours=hours, params=params, beta=0 if case == 4 else None,
                  traffic_multiplier=0 if case == 8 else 1.3, hourly_multiplier={8: 0, 12: 1.7})
    base = demand.estimate_demand(town, **kwargs).total_daily_visitors
    expected = []
    for venue in venues[1:]:
        without = town.model_copy(update={"venues": [v for v in venues if v.id != venue.id]})
        effect = base - demand.estimate_demand(without, **kwargs).total_daily_visitors
        expected.append(dict(venue_id=venue.id, name=venue.name, category=venue.category.value,
                             distance_m=round(math.hypot(venue.x-focal.x, venue.y-focal.y) * params.detour_factor, 1),
                             effect_on_focal_visitors=round(effect, 3),
                             effect_on_focal_pct=round(100 * effect / base, 3) if base > 0 else 0,
                             role="neutral" if abs(effect) < 0.5 else "complement" if effect > 0 else "competitor"))
    expected.sort(key=lambda row: -abs(row["effect_on_focal_visitors"]))
    actual = demand.synergy_analysis(town, **kwargs)
    assert [row.model_dump(mode="json") for row in actual] == expected


@pytest.mark.skipif(not Path("/proc/self/statm").exists(), reason="Linux process-memory accounting is required")
def test_large_neighborhood_synergy_finishes_within_bounded_resources():
    script = textwrap.dedent("""\
        import json, os, resource, time
        from pathlib import Path
        from store_emulator.domain.town import TownSpec
        from store_emulator.engine.town import generate_town, synergy_analysis
        town = generate_town(TownSpec(size_m=3000, density=1, venue_density=4, seed=24102490))
        current = int(Path('/proc/self/statm').read_text().split()[0]) * os.sysconf('SC_PAGE_SIZE')
        resource.setrlimit(resource.RLIMIT_AS, (current + 512 * 1024**2, current + 512 * 1024**2))
        start = time.monotonic()
        rows = synergy_analysis(town)
        print(json.dumps({'rows': [r.model_dump(mode='json') for r in rows],
                          'seconds': time.monotonic()-start,
                          'peak_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}, allow_nan=False))
    """)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            env={**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}, timeout=30)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert len(output["rows"]) == len({row["venue_id"] for row in output["rows"]}) == 1883
    assert any(row["role"] == "competitor" for row in output["rows"])
    assert any(row["role"] == "complement" for row in output["rows"])
    print(f"Dense synergy: {output['seconds']:.3f}s, peak RSS {output['peak_mib']:.1f} MiB")
