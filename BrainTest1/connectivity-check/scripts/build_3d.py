"""
Interactive 3D view of the static connectivity check.

Shows the whole brain + nerve cord as a faint cloud of neuron cell bodies, the
candidate sensory / motor neurons (and the relay neurons between them) at the
positions of their synapses, and the strongest sensory -> relay -> motor paths
as lines between neuron centres.

Run: python scripts/build_3d.py     (first run scans the 13 GB synapse table, a few minutes)
Output: ../output/3d/brain_paths_3d.html  (self-contained, open in any browser)
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pyarrow as pa
import pyarrow.compute as pc

from run_check import DATA, MOTOR_TYPES, OUT, load_candidates

OUT3D = OUT / "3d"
OUT3D.mkdir(parents=True, exist_ok=True)
CACHE = OUT3D / "synapse_points_cache.feather"

NM_PER_VOXEL_UM = 0.008  # 8 nm voxels -> micrometres
PATHS_PER_PAIR = 3
MAX_POINTS = {"sensory": 15000, "motor": 3500, "relay": 9000, "soma": 45000}

GROUP_COLORS = {"johnstons_organ": "#2A9D8F", "looming_lplc": "#E76F51"}
MOTOR_COLOR, RELAY_COLOR = "#FFD166", "#B8A9C9"


def strongest_paths(edges, sensory, motor):
    all_motor = [b for v in motor.values() for b in v]
    motor_type_of = {b: t for t, v in motor.items() for b in v}
    e2 = edges[edges["body_post"].isin(all_motor)]
    rows = []
    for g, sids in sensory.items():
        e1 = edges[edges["body_pre"].isin(sids)]
        j = e1.merge(e2, left_on="body_post", right_on="body_pre", suffixes=("_1", "_2"))
        j = j[~j["body_post_1"].isin(all_motor)]
        j["w"] = np.minimum(j["weight_1"], j["weight_2"])
        j["mtype"] = j["body_post_2"].map(motor_type_of)
        j["group"] = g
        for mt in MOTOR_TYPES:
            rows.append(j[j["mtype"] == mt].nlargest(PATHS_PER_PAIR, "w"))
    p = pd.concat(rows)
    return p.rename(columns={"body_pre_1": "s", "body_post_1": "r", "body_post_2": "m"})[
        ["group", "mtype", "s", "r", "m", "w"]
    ].reset_index(drop=True)


def load_synapse_points(needed: set) -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_feather(CACHE)
    print("scanning synapse table (one-off, several minutes)...")
    needed_arr = pa.array(sorted(needed), type=pa.int64())
    src = pa.memory_map(str(DATA / "syn-points-male-cns-v1.0-minconf-0.5.feather"))
    reader = pa.ipc.open_file(src)
    parts = []
    for i in range(reader.num_record_batches):
        b = reader.get_batch(i).select(["x", "y", "z", "body"])
        mask = pc.is_in(b["body"], value_set=needed_arr)
        if pc.any(mask).as_py():
            parts.append(b.filter(mask).to_pandas())
        if i % 500 == 0:
            print(f"  batch {i}/{reader.num_record_batches}")
    df = pd.concat(parts, ignore_index=True)
    df.to_feather(CACHE)
    return df


def cloud(df, name, color, size, opacity, max_pts, seed=0):
    if len(df) > max_pts:
        df = df.sample(max_pts, random_state=seed)
    return go.Scatter3d(
        x=df["x"] * NM_PER_VOXEL_UM, y=df["y"] * NM_PER_VOXEL_UM, z=df["z"] * NM_PER_VOXEL_UM,
        mode="markers", name=name, marker=dict(size=size, color=color, opacity=opacity),
        hoverinfo="skip",
    )


def main():
    ann = pd.read_feather(DATA / "body-annotations-male-cns-v1.0-minconf-0.5.feather")
    edges = pd.read_feather(DATA / "connectome-weights-male-cns-v1.0-minconf-0.5.feather")
    ids = set(ann["bodyId"])
    edges = edges[edges["body_pre"].isin(ids) & edges["body_post"].isin(ids)]

    sensory, motor = load_candidates(ann)
    paths = strongest_paths(edges, sensory, motor)
    paths.to_csv(OUT / "data" / "strongest_paths_3d.csv", index=False)

    all_sensory = {b for v in sensory.values() for b in v}
    all_motor = {b for v in motor.values() for b in v}
    relays = set(paths["r"])
    pts = load_synapse_points(all_sensory | all_motor | relays)

    type_of = dict(zip(ann["bodyId"], ann["type"].fillna("?")))
    centre = pts.groupby("body")[["x", "y", "z"]].mean() * NM_PER_VOXEL_UM

    fig = go.Figure()

    soma = ann["somaLocation"].dropna()
    soma_xyz = np.stack(soma.to_numpy()) * NM_PER_VOXEL_UM
    if len(soma_xyz) > MAX_POINTS["soma"]:
        soma_xyz = soma_xyz[np.random.default_rng(0).choice(len(soma_xyz), MAX_POINTS["soma"], replace=False)]
    fig.add_trace(go.Scatter3d(
        x=soma_xyz[:, 0], y=soma_xyz[:, 1], z=soma_xyz[:, 2], mode="markers", name="all cell bodies (outline of the CNS)",
        marker=dict(size=1.5, color="#8A7F86", opacity=0.16), hoverinfo="skip"))

    for g, sids in sensory.items():
        fig.add_trace(cloud(pts[pts["body"].isin(sids)], f"{g} synapses", GROUP_COLORS[g], 2.4, 0.6, MAX_POINTS["sensory"]))
    fig.add_trace(cloud(pts[pts["body"].isin(relays)], "relay neurons (on strongest paths)", RELAY_COLOR, 2.6, 0.7, MAX_POINTS["relay"]))
    fig.add_trace(cloud(pts[pts["body"].isin(all_motor)], "motor neurons (DNa01, DNa02, MDN, DNp09)", MOTOR_COLOR, 2.0, 0.5, MAX_POINTS["motor"]))

    for g in sensory:
        xs, ys, zs = [], [], []
        for row in paths[paths["group"] == g].itertuples():
            for b in (row.s, row.r, row.m):
                if b not in centre.index:
                    break
            else:
                for b in (row.s, row.r, row.m):
                    c = centre.loc[b]
                    xs.append(c["x"]); ys.append(c["y"]); zs.append(c["z"])
                xs.append(None); ys.append(None); zs.append(None)
        fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", name=f"strongest paths from {g}",
                                   line=dict(color=GROUP_COLORS[g], width=5), hoverinfo="skip"))

    labelled = pd.concat([paths["s"], paths["r"], paths["m"]]).drop_duplicates()
    labelled = [b for b in labelled if b in centre.index]
    role = {b: "sensory" for b in all_sensory} | {b: "relay" for b in relays} | {b: "motor" for b in all_motor}
    fig.add_trace(go.Scatter3d(
        x=[centre.loc[b, "x"] for b in labelled], y=[centre.loc[b, "y"] for b in labelled], z=[centre.loc[b, "z"] for b in labelled],
        mode="markers+text", name="neurons on paths (hover / labels)",
        text=[type_of.get(b, "?") for b in labelled], textposition="top center", textfont=dict(size=9, color="#F4F1F3"),
        hovertext=[f"{type_of.get(b, '?')}<br>{role[b]}<br>bodyId {b}" for b in labelled], hoverinfo="text",
        marker=dict(size=5, color=[MOTOR_COLOR if role[b] == "motor" else RELAY_COLOR if role[b] == "relay" else "#FFFFFF" for b in labelled],
                    line=dict(width=1, color="#241D22"))))

    axis = dict(showbackground=False, showgrid=False, zeroline=False, showticklabels=False, title="")
    fig.update_layout(
        title="Echo-Fly: strongest sensory -> relay -> motor paths in the male fly CNS (drag to rotate, click legend to toggle)",
        template="plotly_dark", paper_bgcolor="#1E181C", plot_bgcolor="#1E181C",
        scene=dict(xaxis=axis, yaxis=axis, zaxis=axis, aspectmode="data", bgcolor="#1E181C"),
        legend=dict(bgcolor="rgba(50,41,47,0.7)"), margin=dict(l=0, r=0, t=50, b=0),
    )
    out = OUT3D / "brain_paths_3d.html"
    fig.write_html(out, include_plotlyjs=True, full_html=True, default_width="100%", default_height="100vh", config={"responsive": True})
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
