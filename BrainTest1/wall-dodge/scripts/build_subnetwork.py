"""
Cut a small, simulable sub-circuit out of the male CNS connectome for the wall-dodge demo.

  input  : looming-sensitive LPLC1 / LPLC2 / LPLC4 neurons (left and right eye)
  relays : the N neurons that carry the most 2-hop signal from those inputs to the turning neurons
  output : the turning descending neurons DNa01 and DNa02 (left and right)

Every connection among the chosen neurons is kept, signed by the pre-synaptic neuron's predicted
neurotransmitter (acetylcholine +, GABA / glutamate -, everything else treated as excitatory).

Run: python scripts/build_subnetwork.py
Output: ../output/data/subnetwork.npz and subnetwork_summary.json
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent.parent / "output" / "data"
OUT.mkdir(parents=True, exist_ok=True)

N_RELAYS = 400
INHIBITORY = {"gaba", "glutamate"}


def side_from_instance(inst: pd.Series) -> pd.Series:
    s = inst.astype(str).str.extract(r"_([LR])(?:$|\b)")[0]
    return s.map({"L": -1, "R": 1}).fillna(0).astype(int)


def main():
    ann = pd.read_feather(DATA / "body-annotations-male-cns-v1.0-minconf-0.5.feather")
    nt = pd.read_feather(DATA / "body-neurotransmitters-male-cns-v1.0.feather")
    edges = pd.read_feather(DATA / "connectome-weights-male-cns-v1.0-minconf-0.5.feather")
    ids = set(ann["bodyId"])
    edges = edges[edges["body_pre"].isin(ids) & edges["body_post"].isin(ids)]

    sens = ann.loc[ann["type"].isin(["LPLC1", "LPLC2", "LPLC4"]), "bodyId"].astype("int64").to_numpy()
    motor = ann.loc[ann["type"].isin(["DNa01", "DNa02"]), "bodyId"].astype("int64").to_numpy()

    e1 = edges[edges["body_pre"].isin(sens)]
    e2 = edges[edges["body_post"].isin(motor)]
    j = e1.merge(e2, left_on="body_post", right_on="body_pre", suffixes=("_1", "_2"))
    j = j[~j["body_post_1"].isin(motor) & ~j["body_post_1"].isin(sens)]
    j["w"] = np.minimum(j["weight_1"], j["weight_2"])
    relay_rank = j.groupby("body_post_1")["w"].sum().sort_values(ascending=False)
    relays = relay_rank.head(N_RELAYS).index.to_numpy(dtype="int64")

    nodes = np.concatenate([sens, relays, motor])
    role = np.concatenate([np.zeros(len(sens), int), np.ones(len(relays), int), np.full(len(motor), 2)])
    index_of = {b: i for i, b in enumerate(nodes)}

    sub = edges[edges["body_pre"].isin(nodes) & edges["body_post"].isin(nodes)]
    pre = sub["body_pre"].map(index_of).to_numpy()
    post = sub["body_post"].map(index_of).to_numpy()
    syn = sub["weight"].to_numpy()

    nt_of = dict(zip(nt["body"], nt["consensus_nt"].fillna("unknown")))
    nt_names = np.array([nt_of.get(b, "unknown") for b in nodes])
    sign = np.where(np.isin(nt_names, list(INHIBITORY)), -1, 1)

    inst = ann.set_index("bodyId").loc[nodes, "instance"].reset_index(drop=True)
    typ = ann.set_index("bodyId").loc[nodes, "type"].fillna("?").to_numpy()
    side = side_from_instance(inst).to_numpy()

    np.savez_compressed(
        OUT / "subnetwork.npz",
        nodes=nodes, role=role, side=side, sign=sign, types=typ, nt=nt_names,
        pre=pre, post=post, syn=syn,
    )

    def count(mask):
        return int(np.sum(mask))

    summary = {
        "neurons": int(len(nodes)),
        "sensory_LPLC": {"total": count(role == 0), "left": count((role == 0) & (side == -1)), "right": count((role == 0) & (side == 1)), "unknown_side": count((role == 0) & (side == 0))},
        "relays": count(role == 1),
        "motor_DNa": {"total": count(role == 2), "left": count((role == 2) & (side == -1)), "right": count((role == 2) & (side == 1))},
        "connections_kept": int(len(pre)),
        "synapses_kept": int(syn.sum()),
        "inhibitory_neurons": count(sign == -1),
        "relay_types_top10": pd.Series(typ[role == 1]).value_counts().head(10).to_dict(),
        "connections_into_motor": count(role[post] == 2),
        "connections_from_sensory_to_relay": count((role[pre] == 0) & (role[post] == 1)),
    }
    json.dump(summary, open(OUT / "subnetwork_summary.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
