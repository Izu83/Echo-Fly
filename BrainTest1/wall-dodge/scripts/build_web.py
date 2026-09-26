"""
Bake the recorded simulation, the neuron layout and the three.js library into one self-contained 3D page.

Run: python scripts/build_web.py      (after simulate.py)
Output: ../output/web/wall_dodge_3d.html   (works offline, also when double-clicked from disk)

three.js (MIT, https://threejs.org) lives in scripts/vendor/. Browsers refuse to load ES modules
from files on disk, so the two module files are converted to plain inline scripts here:
"export{a as X,...}" becomes "window.THREE={X:a,...}" and the OrbitControls import becomes a
destructuring of window.THREE.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "output"
VENDOR = HERE / "vendor"


def three_as_script() -> str:
    src = (VENDOR / "three.module.min.js").read_text(encoding="utf-8")
    m = re.search(r"export\s*\{([^}]*)\}\s*;?\s*$", src)
    assert m, "three.module.min.js: export list not found"
    pairs = []
    for item in m.group(1).split(","):
        parts = item.strip().split(" as ")
        local, public = (parts[0], parts[-1])
        pairs.append(f"{public}:{local}")
    body = src[: m.start()] + "window.THREE={" + ",".join(pairs) + "};"
    return "(function(){" + body + "})();"


def orbit_as_script() -> str:
    src = (VENDOR / "OrbitControls.js").read_text(encoding="utf-8")
    imp = re.search(r"import\s*\{([^}]*)\}\s*from\s*'three'\s*;", src)
    assert imp, "OrbitControls.js: import not found"
    src = src.replace(imp.group(0), "const {" + imp.group(1) + "} = window.THREE;")
    assert "export { OrbitControls };" in src
    src = src.replace("export { OrbitControls };", "window.OrbitControls = OrbitControls;")
    return "(function(){" + src + "})();"


def main():
    trials = json.load(open(OUT / "data" / "trials_for_3d.json"))
    summary = json.load(open(OUT / "data" / "results_summary.json"))
    layout = json.load(open(OUT / "data" / "layout.json"))
    payload = {"params": trials["params"], "control_ms": trials["control_ms"], "modes": trials["modes"], "summary": summary, "layout": layout}

    html = (HERE / "wall_dodge_template.html").read_text(encoding="utf-8")
    libs = (three_as_script() + "\n" + orbit_as_script()).replace("</script", "<\\/script")
    assert "/*__THREE__*/" in html
    html = html.replace("/*__THREE__*/", libs, 1)
    html = html.replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")), 1)

    out = OUT / "web" / "wall_dodge_3d.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e3:.0f} kB)")



if __name__ == "__main__":
    main()
