// Spiking sub-circuit of the fly brain: LPLC1/2/4 looming neurons -> 400 relays -> DNa01/DNa02.
// Same leaky integrate-and-fire model as experiments/wall-dodge/scripts/brain.py (1 ms steps,
// rest/reset -52 mV, threshold -45 mV, tau_m 20 ms, tau_syn 5 ms, 2 ms refractory, 2 ms delay,
// 0.275 mV per synapse times one global gain). Works in the browser and in Node.
(function (root) {
  "use strict";

  const V_REST = -52, V_RESET = -52, V_TH = -45;
  const TAU_M = 20, TAU_SYN = 5, DT = 1;
  const REFRAC_STEPS = 2, DELAY_STEPS = 2;
  const W_SYN = 0.275;   // mV per synapse
  const W_INPUT = 14;    // mV kick per external input spike

  // small fast seeded random generator, so a run can be replayed exactly
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function poisson(rng, lam) {
    if (lam <= 0) return 0;
    const L = Math.exp(-lam);
    let k = 0, p = rng();
    while (p > L) { k++; p *= rng(); }
    return k;
  }

  class FlyBrain {
    // opts: gain (number), swapEyes (bool: left eye wired into the right side), seed (int)
    constructor(data, opts = {}) {
      const gain = opts.gain ?? 2.0;
      this.data = data;
      this.n = data.n;
      this.rng = mulberry32(opts.seed ?? 1);

      const w = new Float32Array(data.targets.length);
      for (let pre = 0; pre < this.n; pre++) {
        const s = data.sign[pre] * W_SYN * gain;
        for (let k = data.offsets[pre]; k < data.offsets[pre + 1]; k++) w[k] = s * data.syn[k];
      }
      this.w = w;
      this.offsets = Int32Array.from(data.offsets);
      this.targets = Int32Array.from(data.targets);

      const idx = (f) => data.role.map((r, i) => (f(r, data.side[i]) ? i : -1)).filter((i) => i >= 0);
      const eyeSide = opts.swapEyes ? 1 : -1;
      this.sensLeft = Int32Array.from(idx((r, s) => r === 0 && s === eyeSide));
      this.sensRight = Int32Array.from(idx((r, s) => r === 0 && s === -eyeSide));
      this.relays = Int32Array.from(idx((r) => r === 1));
      this.dnaLeft = Int32Array.from(idx((r, s) => r === 2 && s === -1));
      this.dnaRight = Int32Array.from(idx((r, s) => r === 2 && s === 1));

      this.decaySyn = Math.exp(-DT / TAU_SYN);
      this.reset();
    }

    reset() {
      const n = this.n;
      this.v = new Float32Array(n).fill(V_REST);
      this.g = new Float32Array(n);
      this.refrac = new Uint8Array(n);
      this.ring = [];
      for (let i = 0; i < DELAY_STEPS; i++) this.ring.push({ list: new Int32Array(n), len: 0 });
      this.counts = new Uint16Array(n);   // spikes since the last takeCounts()
      this.t = 0;
    }

    _drive(group, rateHz) {
      if (rateHz <= 0) return;
      const lam = (rateHz * DT) / 1000, rng = this.rng, g = this.g;
      for (let i = 0; i < group.length; i++) {
        const k = poisson(rng, lam);
        if (k) g[group[i]] += k * W_INPUT;
      }
    }

    // Advance 1 ms. input: {eyeLeft, eyeRight} Hz onto each LPLC neuron of that eye,
    // {dnaLeft, dnaRight} Hz of extra input straight onto the turning neurons (compass + spontaneous).
    step(input) {
      const { v, g, refrac, counts, w, offsets, targets } = this;
      const slot = this.t % DELAY_STEPS;
      const arriving = this.ring[slot];

      for (let i = 0; i < this.n; i++) g[i] *= this.decaySyn;
      for (let a = 0; a < arriving.len; a++) {
        const pre = arriving.list[a];
        for (let k = offsets[pre]; k < offsets[pre + 1]; k++) g[targets[k]] += w[k];
      }
      this._drive(this.sensLeft, input.eyeLeft);
      this._drive(this.sensRight, input.eyeRight);
      this._drive(this.dnaLeft, input.dnaLeft || 0);
      this._drive(this.dnaRight, input.dnaRight || 0);

      const out = arriving;   // reuse this slot for the spikes of this step
      out.len = 0;
      const k = DT / TAU_M;
      for (let i = 0; i < this.n; i++) {
        let vi = v[i] + k * (V_REST - v[i] + g[i]);
        if (refrac[i] > 0) { vi = V_RESET; refrac[i]--; }
        if (vi >= V_TH) {
          vi = V_RESET;
          refrac[i] = REFRAC_STEPS;
          out.list[out.len++] = i;
          counts[i]++;
        }
        v[i] = vi;
      }
      this.t++;
      return out;
    }

    // mean rate (Hz) of a group over `ms` milliseconds of counts
    rate(group, ms) {
      let s = 0;
      for (let i = 0; i < group.length; i++) s += this.counts[group[i]];
      return (s / group.length) * (1000 / ms);
    }

    clearCounts() { this.counts.fill(0); }
  }

  root.FlyBrain = FlyBrain;
  root.mulberry32 = mulberry32;
})(typeof window !== "undefined" ? window : globalThis);
