"""Compare captured source samples; not a live browser/sink delivery assertion."""
import json
import sys
from pathlib import Path
from parity_check import assert_close, run_py, run_ts

cases = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
assert len({case['source'] for case in cases}) == 6
ts = run_ts(cases)
py = run_py(cases)
total = 0
for case in cases:
    name = case['name']
    assert len(ts[name]) == len(py[name])
    for index, (left, right) in enumerate(zip(ts[name], py[name])):
        for field in left:
            assert_close(name, index, field, left[field], right[field])
        total += 1
    print(json.dumps(dict(source=case['source'], series=name, points=len(ts[name]), passed=True)))
print(json.dumps(dict(passed=True, sources=6, series=len(cases), points=total,
                      scope='captured identical timestamps/values, TS versus Python, all output fields')))
