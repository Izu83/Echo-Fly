"""Charts for the wall-dodge results. Run after simulate.py: python scripts/plot_results.py"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent.parent / "output"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})
S = json.load(open(OUT / "data" / "results_summary.json"))
T = json.load(open(OUT / "data" / "trials_for_3d.json"))

labels = {"brain": "real wiring", "swapped": "eyes swapped", "scrambled_eyes": "eyes scrambled", "random": "no brain\n(random side)"}
colors = {"brain": "#2A9D8F", "swapped": "#E76F51", "scrambled_eyes": "#E76F51", "random": "#8A7F86"}

fig, ax = plt.subplots(figsize=(7, 4.2))
for i, (m, v) in enumerate(S["modes"].items()):
    lo, hi = v["ci95"]
    ax.bar(i, v["accuracy"] * 100, color=colors[m], yerr=[[max(0, v["accuracy"] - lo) * 100], [max(0, hi - v["accuracy"]) * 100]], capsize=4)
    ax.text(i, v["accuracy"] * 100 + 6, f"{v['accuracy']:.0%}", ha="center", fontweight="bold")
ax.axhline(50, color="#4A3D46", ls="--"); ax.text(-0.45, 51.5, "chance (50%)", ha="left", color="#4A3D46")
ax.set_xticks(range(4), [labels[m] for m in S["modes"]]); ax.set_ylim(0, 112); ax.set_ylabel("walls dodged (%)")
ax.set_title(f"Wall dodge accuracy ({S['n_trials']} random walls per bar, 95% CI)")
fig.tight_layout(); fig.savefig(OUT / "graphs" / "accuracy_by_condition.png", dpi=150); plt.close(fig)

sw = S["gain_sweep_brain_accuracy"]
fig, ax = plt.subplots(figsize=(6, 3.8))
gains = list(sw["by_gain"]); ax.plot([float(g) for g in gains], [sw["by_gain"][g] * 100 for g in gains], "o-", color="#2A9D8F")
ax.axvline(S["gain"], color="#4A3D46", ls="--"); ax.text(S["gain"] + 0.05, 8, "used", color="#4A3D46")
ax.set_xlabel("global synaptic gain"); ax.set_ylabel("walls dodged (%)"); ax.set_ylim(0, 105)
ax.set_title(f"Robustness to the one free parameter ({sw['n_trials']} walls each)")
fig.tight_layout(); fig.savefig(OUT / "graphs" / "gain_sweep.png", dpi=150); plt.close(fig)

for k, (mode, idx) in enumerate([("brain", 0), ("brain", 1)]):
    tr = T["modes"][mode][idx]; fr = tr["frames"]; t = [i * T["control_ms"] / 1000 for i in range(len(fr))]
    fig, ax = plt.subplots(3, 1, figsize=(7.5, 6.2), sharex=True)
    ax[0].plot(t, [f[2] for f in fr], color="#FF8FA3", label="left eye input"); ax[0].plot(t, [f[3] for f in fr], color="#264653", label="right eye input")
    ax[0].set_ylabel("looming input (Hz)"); ax[0].legend(frameon=False)
    ax[1].plot(t, [f[7] for f in fr], color="#E9C46A", label="DNa left"); ax[1].plot(t, [f[8] for f in fr], color="#6D597A", label="DNa right")
    ax[1].set_ylabel("steering neurons (Hz)"); ax[1].legend(frameon=False)
    ax[2].plot(t, [f[1] for f in fr], color="#2A9D8F"); ax[2].axhspan(tr["gap"] - 4 + 0.8, tr["gap"] + 4 - 0.8, color="#7be0a0", alpha=.25, label="safe zone (fits through the gap)")
    ax[2].set_ylabel("fly sideways position"); ax[2].set_xlabel("time (s)  -  wall arrives at 3 s"); ax[2].legend(frameon=False, loc="best")
    fig.suptitle(f"Example wall: gap on the {'right' if tr['gap'] > 0 else 'left'} -> {'dodged' if tr['dodged'] else 'hit'}")
    fig.tight_layout(); fig.savefig(OUT / "graphs" / f"example_trial_{k + 1}.png", dpi=150); plt.close(fig)
print("ok")
