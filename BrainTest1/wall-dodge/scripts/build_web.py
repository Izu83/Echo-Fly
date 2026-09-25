"""
Bake the recorded simulation into one self-contained 3D page.

Run: python scripts/build_web.py      (after simulate.py)
Output: ../output/web/wall_dodge_3d.html   (needs internet once per session for the three.js library)
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "output"


def main():
    trials = json.load(open(OUT / "data" / "trials_for_3d.json"))
    summary = json.load(open(OUT / "data" / "results_summary.json"))
    payload = {"params": trials["params"], "control_ms": trials["control_ms"], "modes": trials["modes"], "summary": summary}
    html = (HERE / "wall_dodge_template.html").read_text(encoding="utf-8")
    html = html.replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")))
    out = OUT / "web" / "wall_dodge_3d.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
