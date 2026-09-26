"""
Give each of the 820 simulated neurons a real position in the brain, and pick the strongest
connections to draw, for the brain-activity panel of the 3D page.

Positions are the neurons' cell-body locations from the connectome annotations (micrometres),
turned so the view matches the fly seen from behind: screen-right = the fly's right, up = dorsal.

Run: python scripts/build_layout.py     (after build_subnetwork.py)
Output: ../output/data/layout.json
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parent.parent / "data"
OUT = HERE.parent / "output" / "data"

N_STRONG_EDGES = 220
N_MOTOR_EDGES = 60
NM_PER_VOXEL_UM = 0.008


def main():
    d = np.load(OUT / "subnetwork.npz", allow_pickle=True)
    nodes, role, side, sign, types = d["nodes"], d["role"], d["side"], d["sign"], d["types"]
    pre, post, syn = d["pre"], d["post"], d["syn"]

    ann = pd.read_feather(DATA / "body-annotations-male-cns-v1.0-minconf-0.5.feather").set_index("bodyId")
    soma = ann.loc[nodes, "somaLocation"]
    assert soma.notna().all(), "some neurons have no soma position"
    p = np.stack([np.asarray(v, dtype=float) for v in soma]) * NM_PER_VOXEL_UM
    c = p.mean(axis=0)
    # x grows toward the fly's left, so mirror it; z is dorsal-up; y (front-back) becomes depth
    view = np.stack([-(p[:, 0] - c[0]), p[:, 2] - c[2], p[:, 1] - c[1]], axis=1)

    keep = pre != post
    e = pd.DataFrame({"pre": pre[keep], "post": post[keep], "syn": syn[keep]})
    strong = e.nlargest(N_STRONG_EDGES, "syn")
    into_motor = e[role[e["post"].to_numpy()] == 2].nlargest(N_MOTOR_EDGES, "syn")
    edges = pd.concat([strong, into_motor]).drop_duplicates(["pre", "post"])
    edge_list = [[int(a), int(b), int(s), int(sign[a])] for a, b, s in edges[["pre", "post", "syn"]].itertuples(index=False)]

    layout = {
        "n": int(len(nodes)),
        "role": role.astype(int).tolist(),
        "side": side.astype(int).tolist(),
        "type": [str(t) for t in types],
        "pos": np.round(view, 1).tolist(),
        "edges": edge_list,
    }
    json.dump(layout, open(OUT / "layout.json", "w"), separators=(",", ":"))
    print(f"wrote layout.json: {len(nodes)} neurons, {len(edge_list)} drawn connections")


if __name__ == "__main__":
    main()
