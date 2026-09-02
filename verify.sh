#!/usr/bin/env bash
set -Eeuo pipefail
python3 -m compileall -q omega
python3 - <<'PY'
from omega.catalog import load_skills, load_agents
assert len(load_skills()) == 100
assert len(load_agents()) == 12
for sid, s in load_skills().items():
    assert s["billing"]["reservation"] > 0
    assert s["prompt"].strip()
print("catalog=PASS skills=100 agents=12")
PY
python3 -m omega db-check
python3 - <<'PY'
from omega.rate_limit import redis
assert redis.ping() is True
print("redis=PASS")
PY
echo "OMEGA production verification PASS"
