"""Merge the authored content packs and board chapter maps into backend/data/curriculum.json.

    python scripts/build_curriculum.py            # writes the file
    python scripts/build_curriculum.py --check    # exits 1 if the committed file is out of date
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "content_src"
OUT = ROOT / "backend" / "data" / "curriculum.json"
LABELS = {"CBSE": "CBSE (NCERT)", "ICSE": "ICSE", "TELANGANA": "Telangana State Board"}


def build() -> dict:
    skeleton = {t["id"]: t for t in json.loads((SRC / "skeleton.json").read_text())}
    T = {}
    for f in sorted((SRC / "content").glob("*.json")):
        for tid, v in json.loads(f.read_text()).items():
            s = skeleton[tid]
            qs = []
            for i, q in enumerate(v["questions"]):
                opts = []
                for x in q["o"]:
                    o = {"t": x["t"]}
                    if x.get("ok"):
                        o["ok"] = 1
                    else:
                        o["m"] = x["m"]
                        if x.get("g") and x["g"] in s["prereqs"]:     # a trace target must be a real prerequisite
                            o["g"] = x["g"]
                    opts.append(o)
                qs.append({"id": f"{tid}_{i}", "lvl": q["lvl"], "q": q["q"], "why": q["why"], "o": opts})
            T[tid] = {"id": tid, "sub": s["subject"], "cls": s["class"], "name": s["name"], "pre": s["prereqs"],
                      "te": v["tags"]["te"], "hi": v["tags"]["hi"], "lesson": v["lesson"], "qs": qs, "steps": v.get("steps")}
    B = {}
    for b, label in LABELS.items():
        m = json.loads((SRC / "map" / f"{b}.json").read_text())
        B[b] = {"label": label, "classes": {}}
        for c, subs in m["classes"].items():
            B[b]["classes"][c] = {s: [{"name": ch["name"], "topics": [t for t in ch["topics"] if t in T]}
                                      for ch in chs if any(t in T for t in ch["topics"])] for s, chs in subs.items()}
    return {"T": T, "B": B}


if __name__ == "__main__":
    text = json.dumps(build(), ensure_ascii=False, separators=(",", ":"))
    if "--check" in sys.argv:
        sys.exit(0 if OUT.read_text() == text else 1)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(text) // 1024} KB")
