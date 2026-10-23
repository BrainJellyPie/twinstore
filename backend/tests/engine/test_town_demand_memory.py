"""A neighborhood allowed by the generator must fit a bounded demand working set."""

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.skipif(not Path("/proc/self/statm").exists(), reason="Linux process-memory accounting is required")
def test_dense_maximum_size_neighborhood_stays_within_512_mib_of_extra_memory():
    script = textwrap.dedent("""\
        import json, os, resource, time
        from pathlib import Path
        from store_emulator.domain.town import TownSpec
        from store_emulator.engine.town import generate_town, estimate_demand

        town = generate_town(TownSpec(size_m=3000, density=1, venue_density=4, seed=24102490))
        current = int(Path('/proc/self/statm').read_text().split()[0]) * os.sysconf('SC_PAGE_SIZE')
        resource.setrlimit(resource.RLIMIT_AS, (current + 512 * 1024**2, current + 512 * 1024**2))
        start = time.monotonic()
        report = estimate_demand(town)
        print(json.dumps({'buildings': len(town.buildings), 'venues': len(town.venues),
                          'report': report.model_dump(mode='json'), 'seconds': time.monotonic() - start,
                          'peak_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}, allow_nan=False))
    """)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            env={**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}, timeout=40)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["buildings"] > 10_000 and output["venues"] > 1_500
    report = output["report"]
    assert report["total_daily_visitors"] > 0
    assert report["total_daily_visitors"] == pytest.approx(report["direct_visitors"] + report["linked_visitors"], abs=0.002)
    print(f"Dense neighborhood: {output['seconds']:.3f}s, peak RSS {output['peak_mib']:.1f} MiB")
