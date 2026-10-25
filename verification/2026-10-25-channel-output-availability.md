# Keep online reports available beside unfinished store outputs

Date: 2026-10-25. Based on main `9b95721161e63ffcdedc1357bbc6a24742afee07`.

The actual CPU channel probe again generated a free offer through Qwen3.5-0.8B,
executed the controlled physical purchase and ran 40 real rule-policy online
sessions. Beside the completed physical fixture, it placed a newer running store
run that had written `timeline.json` but not its customer file. The channel reader
selected that unfinished run and raised `FileNotFoundError`. Because the online
analyst reads the same channel facts, an unrelated in-progress save could also
block access to otherwise valid online report context.

Candidate selection now requires the files the reader uses and skips a known
non-completed status. If a completed candidate cannot be decoded or validated,
the automatic comparison tries the next candidate. An explicit unreadable-run
request returns a 409 error; absent/incomplete candidates return 404. Complete
legacy outputs without valid status metadata remain readable. No saved files are
changed by this repair.

The actual CPU reproduction passed after the fix, keeping the older completed
fixture and its full $27 of online payments. Baseline artifacts are under
`/workspace/scratch/cpu-vlm-probe/channels-1792959001842649983`; the fixed run is
`/workspace/scratch/cpu-vlm-probe/channels-1792959122120781664`.

Reproduce with the local server already running:

```bash
PYTHONPATH=backend/src backend/.venv/bin/python verification/local-channel-probe.py --unfinished-neighbor
```

Nine API boundary cases failed before their fixes: partial/running, complete-but-running,
complete-but-failed, incomplete-but-marked-completed, malformed JSON, a missing
customer identity, a wrong timeline shape, and arrays in place of the customer or summary objects. The checks also preserve legacy outputs
with absent or damaged status metadata and verify that the analyst facts still
refer to the valid completed store run.


Focused verification passed: 55 distinct backend tests, strict backend typing
(zero errors/warnings), backend boot and the probe CLI. The first 53 passed in
12.06 seconds; after the two additional malformed-object cases were reproduced
and fixed, all 15 channel API cases passed again and the changed module passed
strict typing. The final actual-model partial-write probe passed; no frontend
source changed in this patch.
