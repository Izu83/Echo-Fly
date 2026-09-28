"""
Leaky integrate-and-fire simulation of the wall-dodge sub-circuit (numpy + scipy sparse).

Neuron model follows the whole-brain fly model of Shiu et al. 2024 (values from memory of the
paper, treat as approximate): rest/reset -52 mV, threshold -45 mV, membrane tau 20 ms,
synaptic tau 5 ms, refractory 2.2 ms, 0.275 mV per synapse, ~1.8 ms transmission delay.
Sensory neurons are driven by Poisson input spikes; everything else only by the connectome.

`GAIN` multiplies every synaptic weight. The sub-circuit is only ~800 of ~200k neurons, so a
gain above 1 is needed for the truncated circuit to carry a usable signal; it is one global
number, applied identically to every connection (never tuned per side or per neuron).
"""

from pathlib import Path

import numpy as np
import scipy.sparse as sp

NPZ = Path(__file__).resolve().parent.parent / "output" / "data" / "subnetwork.npz"

V_REST, V_RESET, V_TH = -52.0, -52.0, -45.0
TAU_M, TAU_SYN = 20.0, 5.0
DT = 1.0            # ms
REFRAC_STEPS = 2
DELAY_STEPS = 2
W_SYN = 0.275       # mV per synapse
W_INPUT = 14.0      # mV kick per Poisson input spike onto a sensory neuron


class Brain:
    def __init__(self, gain=1.0, swap_wires=False, scramble_eyes=False, seed=0):
        d = np.load(NPZ, allow_pickle=True)
        self.nodes, self.role, self.side = d["nodes"], d["role"], d["side"]
        self.types = d["types"]
        self.n = len(self.nodes)
        self.sens = np.where(self.role == 0)[0]
        self.motor = np.where(self.role == 2)[0]
        self.rng = np.random.default_rng(seed)

        pre, post, syn, sign = d["pre"], d["post"], d["syn"], d["sign"]
        w = sign[pre] * W_SYN * syn * gain
        self.W = sp.csr_matrix((w, (post, pre)), shape=(self.n, self.n))

        # which sensory neurons see which eye; swapping the wires feeds the left eye into the right side
        sens_side = self.side[self.sens].copy()
        if swap_wires:
            sens_side = -sens_side
        if scramble_eyes:
            sens_side = np.random.default_rng(seed + 12345).permutation(sens_side)
        self.sens_left = self.sens[sens_side == -1]
        self.sens_right = self.sens[sens_side == 1]
        self.turn_left = self.motor[self.side[self.motor] == -1]
        self.turn_right = self.motor[self.side[self.motor] == 1]
        self.reset()

    def reset(self):
        self.v = np.full(self.n, V_REST)
        self.g = np.zeros(self.n)
        self.refrac = np.zeros(self.n, int)
        self.ring = np.zeros((DELAY_STEPS, self.n))
        self.t = 0

    def step(self, rate_left_hz, rate_right_hz):
        """Advance 1 ms. Returns the boolean spike vector."""
        drive = np.zeros(self.n)
        drive[self.sens_left] = self.rng.poisson(rate_left_hz * DT / 1000.0, len(self.sens_left))
        drive[self.sens_right] = self.rng.poisson(rate_right_hz * DT / 1000.0, len(self.sens_right))

        slot = self.t % DELAY_STEPS
        arriving = self.ring[slot].copy()
        self.g *= np.exp(-DT / TAU_SYN)
        self.g += self.W @ arriving + drive * W_INPUT
        self.v += DT / TAU_M * (V_REST - self.v + self.g)
        self.v[self.refrac > 0] = V_RESET
        self.refrac[self.refrac > 0] -= 1

        spikes = self.v >= V_TH
        self.v[spikes] = V_RESET
        self.refrac[spikes] = REFRAC_STEPS
        self.ring[slot] = spikes.astype(float)
        self.t += 1
        return spikes
