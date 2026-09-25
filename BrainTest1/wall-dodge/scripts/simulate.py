"""
Closed-loop wall-dodge: a stationary-in-depth fly, walls with a gap flying at it, the fly steering
sideways with the output of the spiking sub-circuit.

World (arbitrary units, x = fly's right, distance d = how far the wall still is from the fly):
    wall     : very wide slab with one wide gap (width GAP_W = the left OR right part of the wall is open),
               gap centre at +-(5.5..7) from the fly, so its inner edge is 1.5..3 to one side
    approach : d goes from 60 to 0 at WALL_SPEED units/s
    input    : each eye sees the solid wall on its side of the fly, window +-WINDOW wide; looming
               strength grows as the wall gets closer  ->  Poisson rate to that eye's LPLC neurons
    output   : smoothed firing rate of left vs right DNa turning neurons  ->  sideways velocity
               v_x = STEER * (rate_right - rate_left)      (assumption: a DNa turns the fly toward
               its own side, as reported for DNa02; the brain decides which side that neuron is driven from)
    result   : when d reaches 0 the fly either fits through the gap (dodged) or not (hit)

Modes: brain (natural wiring), swapped (left eye wired into the right side), scrambled_eyes (each input
neuron gets a random eye), random (picks a random side and steers to +-6: chance baseline).

Run: python scripts/simulate.py [n_trials]
Output: ../output/data/results_summary.json and trials_for_3d.json
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

from brain import Brain

OUT = Path(__file__).resolve().parent.parent / "output" / "data"

GAIN = 2.0
D_START, WALL_SPEED = 60.0, 20.0
GAP_W, FLY_HALF = 8.0, 0.8
WINDOW = 6.0
MAX_RATE = 150.0          # Hz onto each LPLC neuron at full looming
LOOM_D0 = 15.0            # looming saturates below ~this distance
CONTROL_MS = 20
SMOOTH = 0.3              # exp smoothing of DNa rate per control step (~50 ms)
STEER = 0.2               # units/s of sideways speed per Hz of left/right DNa difference
V_MAX = 12.0
CTRL_PER_TRIAL = int(D_START / WALL_SPEED * 1000 / CONTROL_MS)
DISPLAY_TRIALS = 12


def solid_fraction(gap_c, x_fly, side):
    lo, hi = (x_fly, x_fly + WINDOW) if side > 0 else (x_fly - WINDOW, x_fly)
    g0, g1 = gap_c - GAP_W / 2, gap_c + GAP_W / 2
    overlap = max(0.0, min(hi, g1) - max(lo, g0))
    return max(0.0, 1.0 - overlap / WINDOW)


def looming(d):
    return min(1.0, LOOM_D0 / (d + 1.0))


def run_trial(mode, gap_c, seed, record=False, gain=None):
    rng = np.random.default_rng(seed)
    brain = None if mode == "random" else Brain(gain=GAIN if gain is None else gain, swap_wires=(mode == "swapped"),
                                                scramble_eyes=(mode == "scrambled_eyes"), seed=seed)
    x, dna_l, dna_r = 0.0, 0.0, 0.0
    random_dir = rng.choice([-1.0, 1.0])
    frames = []
    for k in range(CTRL_PER_TRIAL):
        d = max(0.0, D_START - WALL_SPEED * k * CONTROL_MS / 1000.0)
        loom = looming(d)
        in_l = MAX_RATE * loom * solid_fraction(gap_c, x, -1)
        in_r = MAX_RATE * loom * solid_fraction(gap_c, x, +1)
        if brain is not None:
            cnt = np.zeros(brain.n)
            for _ in range(CONTROL_MS):
                cnt += brain.step(in_l, in_r)
            hz = cnt / (CONTROL_MS / 1000.0)
            dna_l = (1 - SMOOTH) * dna_l + SMOOTH * hz[brain.turn_left].mean()
            dna_r = (1 - SMOOTH) * dna_r + SMOOTH * hz[brain.turn_right].mean()
            vx = float(np.clip(STEER * (dna_r - dna_l), -V_MAX, V_MAX))
            sens_l, sens_r = hz[brain.sens_left].mean(), hz[brain.sens_right].mean()
            relay = hz[brain.role == 1].mean()
        else:
            vx = float(np.clip(3.0 * (random_dir * 6.0 - x), -V_MAX, V_MAX))
            sens_l = sens_r = relay = 0.0
        x += vx * CONTROL_MS / 1000.0
        if record:
            frames.append([round(d, 2), round(x, 3), round(in_l, 1), round(in_r, 1), round(sens_l, 1), round(sens_r, 1),
                           round(relay, 1), round(dna_l, 1), round(dna_r, 1)])
    hit = abs(x - gap_c) > (GAP_W / 2 - FLY_HALF)
    return hit, x, frames


def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(centre - half, 3), round(centre + half, 3)]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    rng = np.random.default_rng(2024)
    gaps = rng.choice([-1, 1], n) * rng.uniform(5.5, 7.0, n)

    summary = {"n_trials": n, "gain": GAIN, "modes": {}}
    display = {}
    for mode in ("brain", "swapped", "scrambled_eyes", "random"):
        t0 = time.time()
        results, frames_out = [], []
        for i, g in enumerate(gaps):
            hit, xf, frames = run_trial(mode, float(g), seed=1000 + i, record=i < DISPLAY_TRIALS)
            results.append((not hit, xf, g))
            if i < DISPLAY_TRIALS:
                frames_out.append({"gap": round(float(g), 3), "dodged": bool(not hit), "final_x": round(xf, 3), "frames": frames})
        ok = int(sum(r[0] for r in results))
        left_gap = [r[0] for r in results if r[2] < 0]
        right_gap = [r[0] for r in results if r[2] > 0]
        summary["modes"][mode] = {
            "dodged": ok, "accuracy": round(ok / n, 3), "ci95": wilson(ok, n),
            "accuracy_gap_left": round(float(np.mean(left_gap)), 3) if left_gap else None,
            "accuracy_gap_right": round(float(np.mean(right_gap)), 3) if right_gap else None,
            "seconds": round(time.time() - t0, 1),
        }
        display[mode] = frames_out
        print(mode, summary["modes"][mode], flush=True)

    sweep = {}
    n_sweep = min(n, 40)
    for gain in (1.0, 1.5, 2.0, 3.0, 4.0):
        ok = sum(not run_trial("brain", float(g), seed=1000 + i, gain=gain)[0] for i, g in enumerate(gaps[:n_sweep]))
        sweep[str(gain)] = round(ok / n_sweep, 3)
        print("gain sweep", gain, sweep[str(gain)], flush=True)
    summary["gain_sweep_brain_accuracy"] = {"n_trials": n_sweep, "by_gain": sweep}

    summary["params"] = dict(D_START=D_START, WALL_SPEED=WALL_SPEED, GAP_W=GAP_W, FLY_HALF=FLY_HALF, WINDOW=WINDOW,
                             MAX_RATE=MAX_RATE, LOOM_D0=LOOM_D0, STEER=STEER, V_MAX=V_MAX, CONTROL_MS=CONTROL_MS)
    json.dump(summary, open(OUT / "results_summary.json", "w"), indent=2)
    json.dump({"params": summary["params"], "control_ms": CONTROL_MS, "modes": display}, open(OUT / "trials_for_3d.json", "w"))


if __name__ == "__main__":
    main()
