// Dopamine learning: plastic connections from "cue" neurons onto the turning neurons (DNa), taught by a
// reward signal (PAM dopamine neurons) and a punishment signal (PPL1 dopamine neurons).
//
//   cue neurons   8 target-direction cells (fire when the current target lies in their direction)
//                 6 wall cells (front / middle / side part of each eye, driven by looming)
//   plastic synapses  cue -> left DNa, cue -> right DNa, as extra input spikes (Hz)
//   eligibility   a synapse is "tagged" when its cue was active while its turning neuron won (the fly turned that way)
//   dopamine      PAM fires when things go better than expected (closer to the target, a wall moving away,
//                 reaching a pickup / goal); PPL1 fires when they go worse (bumping into a wall, a wall
//                 looming closer, walking away from the target)
//   compartments  as in the mushroom body, each dopamine signal only reaches its own synapses:
//                 the target signal (progress, arrival) teaches the target-direction synapses,
//                 the wall signal (bumps, looming) teaches the wall synapses
//   rule          dw = learning rate x (PAM - PPL1 of that compartment) x tag   (a three-factor rule)
//
// This is a model of the idea, not a piece of the connectome: the cue cells and the plastic synapses are
// made up; PAM and PPL1 are the names of the real fly dopamine clusters that signal reward and punishment.
(function (root) {
  "use strict";

  const N_DIR = 8;               // target-direction cells, 45 degrees apart, cell 0 = straight ahead
  const N_WALL = 6;              // left eye front/middle/side, right eye front/middle/side
  const N_CUE = N_DIR + N_WALL;
  const W_MAX = 200;             // Hz: strongest possible plastic synapse (same as the fixed compass)
  const TAU_TAG = 0.6;           // s: how long a synapse stays tagged after it was used
  const BASELINE_RATE = 0.02;    // how fast "what I expect" follows what actually happens

  function cueNames() {
    const dirs = ["ahead", "ahead-right", "right", "behind-right", "behind", "behind-left", "left", "ahead-left"];
    return [...dirs.map((d) => `target ${d}`), "wall L front", "wall L middle", "wall L side", "wall R front", "wall R middle", "wall R side"];
  }

  class Learner {
    constructor(seed = 1) {
      this.w = new Float32Array(N_CUE * 2);      // [cue * 2 + side], side 0 = left DNa, 1 = right DNa
      this.forget(seed);
    }

    // a fresh, naive fly: small random synapses, no preference for any side
    forget(seed = 1) {
      const rng = root.mulberry32(seed * 104729 + 7);
      for (let i = 0; i < this.w.length; i++) this.w[i] = rng() * 0.15 * W_MAX;
      this.episodes = [];
      this.startEpisode();
    }

    startEpisode() {
      this.tag = new Float32Array(N_CUE * 2);
      this.cue = new Float32Array(N_CUE);
      this.expectGoal = 0; this.expectWall = 0;
      this.goalDA = 0; this.wallDA = 0;
      this.prevDist = null;
      this.prevDanger = null;
      this.pam = 0; this.ppl1 = 0;
    }

    // cue activity (0..1) from where the target is and what the eyes see
    sense(run) {
      const c = this.cue, tg = run.target();
      const dx = tg.x - run.x, dy = tg.y - run.y, dist = Math.hypot(dx, dy);
      const err = Math.atan2(dy, dx) - run.heading;
      const sensed = run.s.targetSense === "sight" ? (root.CWS.lineOfSight(run.map, run.x, run.y, tg.x, tg.y) ? 1 : 0) : 1;
      for (let k = 0; k < N_DIR; k++) {
        const a = Math.cos(err - (k * 2 * Math.PI) / N_DIR);
        c[k] = a > 0 ? sensed * a ** 3 : 0;
      }
      const sums = new Float32Array(N_WALL), counts = new Float32Array(N_WALL);
      const per = run.rays.length / 2;
      run.rays.forEach((r, i) => {
        const j = r.side * 3 + Math.min(2, Math.floor(((i % per) * 3) / per));
        sums[j] += r.loom; counts[j]++;
      });
      for (let j = 0; j < N_WALL; j++) c[N_DIR + j] = counts[j] ? sums[j] / counts[j] : 0;
      return dist;
    }

    // extra input (Hz) onto the left and right turning neurons
    drive() {
      let l = 0, r = 0;
      for (let k = 0; k < N_CUE; k++) { l += this.cue[k] * this.w[k * 2]; r += this.cue[k] * this.w[k * 2 + 1]; }
      return [l, r];
    }

    // after the fly moved: work out the dopamine and change the tagged synapses
    // events: { bumped, reached (pickup / goal), dist, danger (strongest looming 0..1), dt, speed }
    learn(run, ev) {
      const s = run.s, dt = ev.dt;
      const decay = Math.exp(-dt / TAU_TAG);
      // the tag says which way the fly actually turned while the cue was active: the turning neuron that
      // fired more than the other gets a positive tag, the other a negative one
      const turnedRight = (run.dnaR - run.dnaL) / 30;
      for (let k = 0; k < N_CUE; k++) {
        const a = this.cue[k] * dt;
        this.tag[k * 2] = this.tag[k * 2] * decay - a * turnedRight;
        this.tag[k * 2 + 1] = this.tag[k * 2 + 1] * decay + a * turnedRight;
      }

      // how well is it going right now, compared with how it usually goes (reward prediction error)?
      // target compartment: getting closer is good.  wall compartment: a wall looming up is bad.
      const progress = this.prevDist == null ? 0 : (this.prevDist - ev.dist) / Math.max(1e-6, ev.speed * dt);
      const looming = this.prevDanger == null ? 0 : (ev.danger - this.prevDanger) / dt;
      this.prevDist = ev.dist;
      this.prevDanger = ev.danger;
      const goalValue = Math.max(-1, Math.min(1, progress));
      const wallValue = -0.5 * Math.max(-2, Math.min(2, looming));
      let goal = goalValue - this.expectGoal, wall = wallValue - this.expectWall;
      this.expectGoal += BASELINE_RATE * (goalValue - this.expectGoal);
      this.expectWall += BASELINE_RATE * (wallValue - this.expectWall);
      if (ev.bumped) wall -= 2;
      if (ev.reached) { goal += 4; this.expectGoal = 0; this.prevDist = null; }
      this.goalDA = goal; this.wallDA = wall;
      this.pam = Math.max(0, goal) + Math.max(0, wall);
      this.ppl1 = Math.max(0, -goal) + Math.max(0, -wall);

      if (!s.learnRate) return;
      const w = this.w, tag = this.tag;
      for (let i = 0; i < w.length; i++) {
        const da = (i >> 1) < N_DIR ? goal : wall;
        w[i] = Math.max(0, Math.min(W_MAX, w[i] + s.learnRate * da * tag[i]));
      }
    }

    // one record per attempt; `pref` = right minus left synapse (Hz) for target-right, target-left,
    // wall-left-front and wall-right-front, so the charts can show how the learning changed over time
    endEpisode(run) {
      const w = this.w, pref = [2, 6, N_DIR, N_DIR + 3].map((k) => Math.round(w[k * 2 + 1] - w[k * 2]));
      this.episodes.push({ ok: run.status === "success", t: +run.t.toFixed(2), bumps: run.bumps, carried: !!run.carrying, mode: run.s.steering, pref });
      if (this.episodes.length > 5000) this.episodes.shift();
    }

    toJSON() {
      return { format: "carry-walk-sim memory", version: 1, w: Array.from(this.w, (v) => +v.toFixed(2)), episodes: this.episodes };
    }
    static fromJSON(obj, seed) {
      const L = new Learner(seed);
      if (obj && obj.w && obj.w.length === L.w.length) { L.w.set(obj.w); L.episodes = obj.episodes || []; }
      else if (obj) throw new Error("not a carry-walk-sim memory file");
      return L;
    }
  }

  root.CWS_LEARN = { Learner, N_CUE, N_DIR, N_WALL, W_MAX, cueNames };
})(typeof window !== "undefined" ? window : globalThis);
