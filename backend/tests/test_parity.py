"""The phone and the server run the same rules. If these drift, offline practice and server truth would disagree."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from app.engine import mastery
from app.engine.planner import readiness

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def js(cur):
    if not NODE:
        pytest.skip("node is not installed")
    r = random.Random(7)
    seq = [[round(r.uniform(0.05, 0.97), 3), r.random() < 0.5] for _ in range(60)]
    out = subprocess.run([NODE, str(ROOT / "scripts" / "js_parity.js"), json.dumps(seq).replace("true", "true")],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return seq, json.loads(out.stdout)


def test_mastery_update_matches(js):
    seq, o = js
    for (p, ok), got in zip(seq, o["nudge"]):
        assert mastery.nudge(p, ok) == pytest.approx(got, abs=1e-12)


def test_levels_match(js):
    _, o = js
    assert o["lvl"] == [mastery.want_level(p) for p in (0.1, 0.39, 0.4, 0.69, 0.7, 0.95)]


def test_prerequisite_closure_matches_in_order(js, cur):
    _, o = js
    for t, pre in o["closure"].items():
        assert cur.all_pre(t) == pre, t


def test_readiness_matches(js, cur):
    _, o = js
    chs = cur.chapters("TELANGANA", 8, "Maths")[:2]
    assert readiness(cur, {"m8_alg": 0.4, "m8_exp": 0.9}, chs) == pytest.approx(o["readiness"], abs=1e-12)
