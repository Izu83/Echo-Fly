"""
Static connectivity check: is there any wiring at all between candidate
"echo-sensing" neurons and the candidate "dodge" motor neurons named in
the main Echo-Fly README, before we spend compute on a spiking simulation?

No dynamics here — just breadth-first reachability over the synaptic
connectivity graph (data/connectome-weights-*.feather), 1 hop = 1 synapse-hop
through the network, regardless of edge weight.

Inputs:
    ../../data/body-annotations-male-cns-v1.0-minconf-0.5.feather
    ../../data/connectome-weights-male-cns-v1.0-minconf-0.5.feather

Outputs (../output/data/ for tables, ../output/graphs/ for images):
    sensory_candidates.csv   every candidate sensory neuron, with annotations
    motor_candidates.csv     every candidate motor neuron, with annotations
    hop_distances.json       shortest hop count from each sensory group to each motor type
    reachability_growth.png  how many neurons become reachable at each hop, per sensory group
    shortest_paths.png       diagram of one example shortest path per (sensory group -> motor type)
    summary.json             machine-readable version of everything above, for the README

Run: python run_check.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent.parent / "output"
GRAPHS = OUT / "graphs"
TABLES = OUT / "data"
GRAPHS.mkdir(parents=True, exist_ok=True)
TABLES.mkdir(parents=True, exist_ok=True)

MAX_HOPS = 6

# Candidate sensory groups: the two input modalities named in the main README
# ("current candidates are the antenna/hearing neurons (Johnston's organ) or
# the 'looming' neurons that detect things rushing at the eyes").
SENSORY_GROUPS = {
    "johnstons_organ": {"type_prefix": "JO-"},
    "looming_lplc": {"type_in": ["LPLC1", "LPLC2", "LPLC4"]},
}

# Candidate motor/descending neurons named in the main README.
# DNp09 is included as "P9" -- Bidaye et al. 2020 named the forward-walking
# descending neuron "P9" before the hemibrain/MANC naming convention (DNp09)
# was assigned to the same cell type; we annotate this explicitly in the output.
MOTOR_TYPES = {
    "DNa01": "turn",
    "DNa02": "turn",
    "MDN": "back up (moonwalker)",
    "DNp09": "walk forward (aka \"P9\", Bidaye et al. 2020)",
}


def load_candidates(ann: pd.DataFrame):
    sensory = {}
    for group, spec in SENSORY_GROUPS.items():
        if "type_prefix" in spec:
            mask = ann["type"].astype(str).str.startswith(spec["type_prefix"])
        else:
            mask = ann["type"].isin(spec["type_in"])
        sensory[group] = ann.loc[mask, "bodyId"].astype("int64").tolist()

    motor = {}
    for mtype in MOTOR_TYPES:
        motor[mtype] = ann.loc[ann["type"] == mtype, "bodyId"].astype("int64").tolist()

    return sensory, motor


def multi_source_bfs(edges: pd.DataFrame, sources: list, max_hops: int):
    """Breadth-first search over body_pre -> body_post edges (direction-aware).

    Returns:
        hop_of: dict bodyId -> hop distance from `sources` (0 = a source itself)
        pred:   dict bodyId -> one predecessor bodyId (for path reconstruction)
        growth: list of (hop, newly_discovered_count, cumulative_count)
    """
    hop_of = {b: 0 for b in sources}
    pred = {}
    frontier = set(sources)
    growth = [(0, len(frontier), len(frontier))]

    for hop in range(1, max_hops + 1):
        if not frontier:
            break
        step = edges[edges["body_pre"].isin(frontier)]
        if step.empty:
            break
        # first predecessor found wins, good enough for an example path
        step = step.drop_duplicates(subset="body_post", keep="first")
        new_mask = ~step["body_post"].isin(hop_of.keys())
        step = step[new_mask]
        if step.empty:
            break
        new_nodes = step["body_post"].tolist()
        new_preds = step["body_pre"].tolist()
        for node, p in zip(new_nodes, new_preds):
            hop_of[node] = hop
            pred[node] = p
        frontier = set(new_nodes)
        growth.append((hop, len(new_nodes), len(hop_of)))

    return hop_of, pred, growth


def reconstruct_path(target: int, pred: dict, sources: set):
    path = [target]
    while path[-1] not in sources:
        if path[-1] not in pred:
            return None  # unreachable / a source with no recorded predecessor
        path.append(pred[path[-1]])
    return list(reversed(path))


def annotate(ids, ann: pd.DataFrame) -> pd.DataFrame:
    cols = ["bodyId", "type", "instance", "class", "superclass", "somaSide"]
    cols = [c for c in cols if c in ann.columns]
    return ann.loc[ann["bodyId"].isin(ids), cols].reset_index(drop=True)


def plot_growth(all_growth: dict, path: Path):
    plt.figure(figsize=(7, 4.5))
    for group, growth in all_growth.items():
        hops = [g[0] for g in growth]
        cumulative = [g[2] for g in growth]
        plt.plot(hops, cumulative, marker="o", label=group)
    plt.xlabel("hops from sensory group")
    plt.ylabel("cumulative neurons reachable")
    plt.title("Reachability growth from each candidate sensory group")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def plot_paths(path_records: list, path: Path, ann_lookup: dict):
    g = nx.DiGraph()
    for rec in path_records:
        chain = rec["path"]
        if chain is None:
            continue
        for a, b in zip(chain[:-1], chain[1:]):
            g.add_edge(a, b)

    if g.number_of_nodes() == 0:
        return

    plt.figure(figsize=(11, 7))
    pos = nx.spring_layout(g, seed=7, k=0.9)
    labels = {n: ann_lookup.get(n, str(n)) for n in g.nodes}
    nx.draw_networkx_nodes(g, pos, node_size=900, node_color="#99E1D9", edgecolors="#32292F")
    nx.draw_networkx_edges(g, pos, arrows=True, arrowsize=14, edge_color="#4A3D46")
    nx.draw_networkx_labels(g, pos, labels=labels, font_size=7)
    plt.title("Example shortest paths: sensory candidates -> motor candidates")
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def main():
    print("loading annotations + weights...")
    ann = pd.read_feather(DATA / "body-annotations-male-cns-v1.0-minconf-0.5.feather")
    edges = pd.read_feather(DATA / "connectome-weights-male-cns-v1.0-minconf-0.5.feather")

    # The raw weight table includes every minconf>=0.5 *segment*, which is mostly tiny
    # unannotated fragments (~88M distinct ids) rather than real, curated neurons
    # (~212k annotated). Restrict the graph to annotated neurons on both ends so hop
    # counts and reachability numbers describe the actual neuron-level connectome.
    annotated_ids = set(ann["bodyId"])
    before = len(edges)
    edges = edges[edges["body_pre"].isin(annotated_ids) & edges["body_post"].isin(annotated_ids)]
    print(f"restricted edges to annotated neurons: {len(edges):,} of {before:,}")

    sensory, motor = load_candidates(ann)

    print("candidate counts:")
    for k, v in sensory.items():
        print(f"  sensory/{k}: {len(v)} neurons")
    for k, v in motor.items():
        print(f"  motor/{k}: {len(v)} neurons")

    all_motor_ids = {bid for ids in motor.values() for bid in ids}

    all_growth = {}
    hop_summary = {}  # sensory group -> motor type -> {hop, path}
    path_records = []

    for group, ids in sensory.items():
        if not ids:
            print(f"WARNING: no neurons found for sensory group '{group}', skipping")
            continue
        print(f"BFS from {group} ({len(ids)} seed neurons)...")
        hop_of, pred, growth = multi_source_bfs(edges, ids, MAX_HOPS)
        all_growth[group] = growth

        hop_summary[group] = {}
        for mtype, mids in motor.items():
            reached = [(m, hop_of[m]) for m in mids if m in hop_of]
            if not reached:
                hop_summary[group][mtype] = {"reachable": False, "min_hop": None}
                continue
            reached.sort(key=lambda x: x[1])
            best_id, best_hop = reached[0]
            path = reconstruct_path(best_id, pred, set(ids))
            hop_summary[group][mtype] = {
                "reachable": True,
                "min_hop": best_hop,
                "example_target_bodyId": int(best_id),
                "example_path": [int(x) for x in path] if path else None,
            }
            path_records.append({"group": group, "motor": mtype, "path": path})

    print("writing candidate tables...")
    all_sensory_ids = [i for ids in sensory.values() for i in ids]
    sens_df = annotate(all_sensory_ids, ann)
    sens_df["sensory_group"] = sens_df["bodyId"].map(
        {i: g for g, ids in sensory.items() for i in ids}
    )
    sens_df.to_csv(TABLES / "sensory_candidates.csv", index=False)

    mot_df = annotate(list(all_motor_ids), ann)
    mot_df["motor_role"] = mot_df["type"].map(MOTOR_TYPES)
    mot_df.to_csv(TABLES / "motor_candidates.csv", index=False)

    print("writing hop_distances.json...")
    with open(TABLES / "hop_distances.json", "w") as f:
        json.dump(hop_summary, f, indent=2)

    print("plotting reachability_growth.png...")
    plot_growth(all_growth, GRAPHS / "reachability_growth.png")

    print("plotting shortest_paths.png...")
    ann_lookup = dict(zip(ann["bodyId"], ann["type"].fillna(ann["bodyId"].astype(str))))
    plot_paths(path_records, GRAPHS / "shortest_paths.png", ann_lookup)

    summary = {
        "max_hops_searched": MAX_HOPS,
        "sensory_group_sizes": {k: len(v) for k, v in sensory.items()},
        "motor_type_sizes": {k: len(v) for k, v in motor.items()},
        "hop_distances": hop_summary,
        "reachability_growth": all_growth,
    }
    with open(TABLES / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("done. see ../output/")


if __name__ == "__main__":
    main()
