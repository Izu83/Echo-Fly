"""
Extra graphs for the static connectivity check: what the candidates are, how strong
the short paths are, which side (left/right) they connect to, and which intermediate
neurons and neurotransmitters carry the signal.

Run after (or independently of) run_check.py:  python extra_graphs.py
Outputs: PNGs to ../output/graphs/, extra_summary.json to ../output/data/.
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from run_check import DATA, GRAPHS, MOTOR_TYPES, SENSORY_GROUPS, TABLES, load_candidates

MULBERRY, TURQ, MUTED = "#32292F", "#2A9D8F", "#8A7F86"
GROUP_COLORS = {"johnstons_organ": "#2A9D8F", "looming_lplc": "#E76F51"}
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10})


def side_of(instance: pd.Series) -> pd.Series:
    s = instance.astype(str).str.extract(r"_([LR])(?:$|\b)")[0]
    return s.fillna("?")


def heatmap(ax, data, rows, cols, title, fmt, cmap="viridis", log=False):
    arr = np.array(data, dtype=float)
    shown = np.log10(arr + 1) if log else arr
    im = ax.imshow(shown, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(cols)), cols)
    ax.set_yticks(range(len(rows)), rows)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            txt = "-" if np.isnan(arr[i, j]) else fmt(arr[i, j])
            r, g_, b_, _ = im.cmap(im.norm(shown[i, j]))
            dark_text = (0.299 * r + 0.587 * g_ + 0.114 * b_) > 0.55
            ax.text(j, i, txt, ha="center", va="center", color="black" if dark_text else "white", fontsize=9, fontweight="bold")
    ax.set_title(title, fontsize=11)
    return im


def main():
    ann = pd.read_feather(DATA / "body-annotations-male-cns-v1.0-minconf-0.5.feather")
    nt = pd.read_feather(DATA / "body-neurotransmitters-male-cns-v1.0.feather")
    edges = pd.read_feather(DATA / "connectome-weights-male-cns-v1.0-minconf-0.5.feather")
    ids = set(ann["bodyId"])
    edges = edges[edges["body_pre"].isin(ids) & edges["body_post"].isin(ids)]

    sensory, motor = load_candidates(ann)
    all_motor = [b for v in motor.values() for b in v]
    type_of = dict(zip(ann["bodyId"], ann["type"].fillna("?")))
    side = dict(zip(ann["bodyId"], side_of(ann["instance"])))
    motor_type_of = {b: t for t, v in motor.items() for b in v}
    summary = {}

    # ---- 1. what the candidates are -------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    jo = ann[ann["bodyId"].isin(sensory["johnstons_organ"])]["type"].value_counts().head(12)
    axes[0].barh(jo.index[::-1], jo.values[::-1], color=GROUP_COLORS["johnstons_organ"])
    axes[0].set_title(f"Johnston's organ candidates ({len(sensory['johnstons_organ'])} neurons)\ntop 12 subtypes")
    axes[0].set_xlabel("neurons")
    lp = ann[ann["bodyId"].isin(sensory["looming_lplc"])].copy()
    lp["side"] = side_of(lp["instance"])
    tab = lp.groupby(["type", "side"]).size().unstack(fill_value=0)
    tab.plot(kind="bar", ax=axes[1], color=["#E76F51", "#264653"], width=0.7)
    axes[1].set_title(f"Looming (LPLC) candidates ({len(sensory['looming_lplc'])} neurons)\nby type and side")
    axes[1].set_ylabel("neurons")
    axes[1].tick_params(axis="x", rotation=0)
    axes[1].legend(title="soma side")
    fig.tight_layout()
    fig.savefig(GRAPHS / "candidates_breakdown.png", dpi=150)
    plt.close(fig)

    # ---- 2. new neurons per hop -----------------------------------------------------
    growth = json.load(open(TABLES / "summary.json"))["reachability_growth"]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    w = 0.38
    for k, (g, rows) in enumerate(growth.items()):
        hops = np.array([r[0] for r in rows])
        new = [r[1] for r in rows]
        ax.bar(hops + (k - 0.5) * w, new, w, label=g, color=GROUP_COLORS[g])
        for h, n in zip(hops, new):
            ax.text(h + (k - 0.5) * w, n, f"{n:,}", ha="center", va="bottom", fontsize=7, rotation=90)
    ax.set_xlabel("hop")
    ax.set_ylabel("neurons first reached at this hop")
    ax.set_title("Where the signal spreads: newly reached neurons per hop")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)
    ax.legend()
    fig.tight_layout()
    fig.savefig(GRAPHS / "new_neurons_per_hop.png", dpi=150)
    plt.close(fig)

    # ---- 3. path strength (direct + 2-hop) ------------------------------------------
    # 2-hop strength of a path s->m->t is min(w(s,m), w(m,t)), the weakest link (synapse count).
    strength = {}      # (group, motor_type) -> {"direct": x, "twohop": y, "paths": n}
    inter_by_group = {}
    lr = {}            # (group, sens_side, motor_side) -> 2-hop strength, turning neurons only
    for g, sids in sensory.items():
        e1 = edges[edges["body_pre"].isin(sids)]
        e2 = edges[edges["body_post"].isin(all_motor)]
        direct = e1[e1["body_post"].isin(all_motor)]
        j = e1.merge(e2, left_on="body_post", right_on="body_pre", suffixes=("_1", "_2"))
        j = j[~j["body_post_1"].isin(all_motor)]  # intermediate must not itself be a motor candidate
        j["w"] = np.minimum(j["weight_1"], j["weight_2"])
        j["mtype"] = j["body_post_2"].map(motor_type_of)
        for mt in MOTOR_TYPES:
            d = direct[direct["body_post"].map(motor_type_of) == mt]
            jj = j[j["mtype"] == mt]
            strength[(g, mt)] = {"direct": int(d["weight"].sum()), "twohop": int(jj["w"].sum()), "paths": int(len(jj))}
        inter = j.assign(itype=j["body_post_1"].map(type_of)).groupby("itype")["w"].sum().sort_values(ascending=False)
        inter_by_group[g] = inter
        j["sside"] = j["body_pre_1"].map(side)
        j["mside"] = j["body_post_2"].map(side)
        turn = j[j["mtype"].isin(["DNa01", "DNa02"])]
        for (s, m), val in turn.groupby(["sside", "mside"])["w"].sum().items():
            lr[(g, s, m)] = int(val)
        # keep intermediates (with weights) for the NT plot
        inter_by_group[g + "_raw"] = j[["body_post_1", "w"]]

    groups = list(sensory)
    mtypes = list(MOTOR_TYPES)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    hops = json.load(open(TABLES / "hop_distances.json"))
    hm = [[hops[g][m]["min_hop"] if hops[g][m]["reachable"] else np.nan for m in mtypes] for g in groups]
    heatmap(axes[0], hm, groups, mtypes, "Minimum hops (sensory group -> motor type)", lambda v: f"{int(v)}", cmap="viridis_r")
    tw = [[strength[(g, m)]["twohop"] for m in mtypes] for g in groups]
    im = heatmap(axes[1], tw, groups, mtypes, "2-hop path strength",
                 lambda v: f"{int(v):,}", cmap="magma", log=True)
    fig.tight_layout()
    fig.savefig(GRAPHS / "hops_and_strength_heatmap.png", dpi=150)
    plt.close(fig)

    # ---- 4. left/right wiring onto the turning neurons ------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, g in zip(axes, groups):
        mat = [[lr.get((g, s, m), 0) for m in ["L", "R"]] for s in ["L", "R"]]
        heatmap(ax, mat, ["sensory L", "sensory R"], ["DNa01/02 L", "DNa01/02 R"],
                f"{g}: 2-hop strength onto turning neurons", lambda v: f"{int(v):,}", cmap="magma", log=True)
    fig.tight_layout()
    fig.savefig(GRAPHS / "left_right_wiring.png", dpi=150)
    plt.close(fig)

    # ---- 5. top intermediate cell types ---------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, g in zip(axes, groups):
        top = inter_by_group[g].head(12)
        ax.barh(top.index[::-1], top.values[::-1], color=GROUP_COLORS[g])
        ax.set_title(f"{g}: top relay cell types\n(2-hop paths to any motor candidate)")
        ax.set_xlabel("summed path strength")
    fig.tight_layout()
    fig.savefig(GRAPHS / "top_relay_cell_types.png", dpi=150)
    plt.close(fig)

    # ---- 6. neurotransmitters of the relays -----------------------------------------
    nt_of = dict(zip(nt["body"], nt["consensus_nt"].fillna("unknown")))
    order = ["acetylcholine", "gaba", "glutamate", "unknown", "other"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    nt_summary = {}
    bottoms = np.zeros(len(groups))
    fracs = {}
    for k, g in enumerate(groups):
        raw = inter_by_group[g + "_raw"].copy()
        raw["nt"] = raw["body_post_1"].map(nt_of).fillna("unknown")
        raw["nt"] = raw["nt"].where(raw["nt"].isin(order[:3]), "other")
        by = raw.groupby("nt")["w"].sum()
        tot = by.sum()
        nt_summary[g] = {n: round(float(by.get(n, 0) / tot), 4) for n in order if n != "unknown"}
        for n in order:
            fracs.setdefault(n, []).append(float(by.get(n, 0) / tot))
    colors = {"acetylcholine": "#2A9D8F", "gaba": "#E76F51", "glutamate": "#E9C46A", "unknown": "#B9AEB5", "other": "#6D597A"}
    for n in order:
        vals = np.array(fracs[n])
        ax.bar(groups, vals, bottom=bottoms, label=n, color=colors[n])
        for i, v in enumerate(vals):
            if v > 0.04:
                ax.text(i, bottoms[i] + v / 2, f"{v:.0%}", ha="center", va="center", color="white", fontsize=9)
        bottoms += vals
    ax.set_ylabel("share of 2-hop path strength")
    ax.set_title("Predicted neurotransmitter of the relay (middle) neurons\nacetylcholine = mostly excitatory, GABA/glutamate = mostly inhibitory in the fly brain")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(GRAPHS / "relay_neurotransmitters.png", dpi=150)
    plt.close(fig)

    summary["path_strength"] = {f"{g}->{m}": v for (g, m), v in strength.items()}
    summary["left_right_2hop_turning"] = {f"{g}:{s}->{m}": v for (g, s, m), v in lr.items()}
    summary["relay_neurotransmitter_share"] = nt_summary
    summary["top_relay_types"] = {g: {k: int(v) for k, v in inter_by_group[g].head(8).items()} for g in groups}
    with open(TABLES / "extra_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
