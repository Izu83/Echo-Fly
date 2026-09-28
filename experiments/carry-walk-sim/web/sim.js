// The 2D world and one run of a fly walking in it, driven by the FlyBrain sub-circuit.
// Units: 1 = one map cell. Angles: radians, screen coordinates (y points down), so a positive
// turn is clockwise on screen = a right turn for the fly.
(function (root) {
  "use strict";

  const TASKS = {
    walk: { label: "Walk A → B", markers: ["start", "goal"] },
    carry: { label: "Carry", markers: ["start", "pickup", "drop"] },
  };

  const DEFAULTS = {
    walkSpeed: 3.0,     // cells/s
    carrySlow: 0.75,    // walking speed factor while carrying the load
    eyeRange: 7.0,      // cells an eye can see
    loomNear: 1.5,      // an obstacle this close (cells) fills the eye completely: looming = 1
    eyeFov: 100,        // degrees each eye covers, from straight ahead to the side
    maxRate: 150,       // Hz onto each LPLC neuron at full looming (same as wall-dodge)
    turnGain: 0.06,     // rad/s of turning per Hz of (right DNa - left DNa)
    maxTurn: 5.0,       // rad/s
    steering: "learned", // how the fly finds its target: "learned" (dopamine) | "compass" (fixed) | "none"
    compass: 200,       // Hz onto the turning neurons on the target's side when the target is 60+ deg off
    learnRate: 60,      // how much one dopamine burst changes a tagged synapse (0 = learning off)
    targetSense: "smell", // "smell": the fly senses the target through walls | "sight": only in line of sight
    innate: 1,          // 1 = the eyes drive the connectome's LPLC neurons (built-in wall avoidance), 0 = off
    randomStart: 1,     // training: face a random direction at the start of every attempt
    spontaneous: 60,    // Hz of random input onto each turning neuron (spontaneous activity)
    gain: 2.0,          // global synaptic gain (same as wall-dodge)
    wiring: "normal",   // "normal" | "swapped" (control: each eye wired into the other side)
    timeLimit: 180,     // simulated seconds before the run counts as failed
    seed: 1,
  };

  const CONTROL_MS = 20;       // brain runs this many 1 ms steps between two movement updates
  const SMOOTH = 0.3;          // exponential smoothing of the turning-neuron rates (~50 ms)
  const FLY_R = 0.3;           // fly body radius, cells
  const REACH = 0.9;           // how close the fly has to get to a marker, cells
  const RAY_STEP = 0.1;        // ray-march step, cells
  const N_RAYS = 11;           // rays per eye

  // ---------- map ----------
  function emptyMap(task, w = 64, h = 40) {
    const m = { task, w, h, grid: new Uint8Array(w * h), start: { x: 4.5, y: h / 2, heading: 0 } };
    if (task === "walk") m.goal = { x: w - 4.5, y: h / 2 };
    else { m.pickup = { x: w / 2, y: h / 2 }; m.drop = { x: w - 4.5, y: h / 2 }; }
    return m;
  }

  function isWall(map, x, y) {
    const cx = Math.floor(x), cy = Math.floor(y);
    if (cx < 0 || cy < 0 || cx >= map.w || cy >= map.h) return true;
    return map.grid[cy * map.w + cx] === 1;
  }

  function blocked(map, x, y, r) {
    for (let cy = Math.floor(y - r); cy <= Math.floor(y + r); cy++)
      for (let cx = Math.floor(x - r); cx <= Math.floor(x + r); cx++) {
        if (!isWall(map, cx + 0.5, cy + 0.5)) continue;
        const nx = Math.max(cx, Math.min(x, cx + 1)), ny = Math.max(cy, Math.min(y, cy + 1));
        if ((nx - x) ** 2 + (ny - y) ** 2 < r * r) return true;
      }
    return false;
  }

  function castRay(map, x, y, ang, range) {
    const dx = Math.cos(ang) * RAY_STEP, dy = Math.sin(ang) * RAY_STEP;
    for (let d = 0; d < range; d += RAY_STEP, x += dx, y += dy) if (isWall(map, x, y)) return d;
    return range;
  }

  function lineOfSight(map, x0, y0, x1, y1) {
    const d = Math.hypot(x1 - x0, y1 - y0);
    return castRay(map, x0, y0, Math.atan2(y1 - y0, x1 - x0), d) >= d - RAY_STEP;
  }

  function wrap(a) {
    while (a > Math.PI) a -= 2 * Math.PI;
    while (a <= -Math.PI) a += 2 * Math.PI;
    return a;
  }

  function mapToJSON(map) {
    let rows = [];
    for (let y = 0; y < map.h; y++) {
      let s = "";
      for (let x = 0; x < map.w; x++) s += map.grid[y * map.w + x] ? "#" : ".";
      rows.push(s);
    }
    const out = { format: "carry-walk-sim map", version: 1, task: map.task, w: map.w, h: map.h, rows };
    for (const k of TASKS[map.task].markers) out[k] = map[k];
    return out;
  }

  function mapFromJSON(obj) {
    if (!obj || !TASKS[obj.task] || !Array.isArray(obj.rows)) throw new Error("not a carry-walk-sim map file");
    const m = emptyMap(obj.task, obj.w, obj.h);
    obj.rows.forEach((row, y) => { for (let x = 0; x < m.w; x++) m.grid[y * m.w + x] = row[x] === "#" ? 1 : 0; });
    for (const k of TASKS[obj.task].markers) if (obj[k]) m[k] = { ...m[k], ...obj[k] };
    return m;
  }

  function cloneMap(m) {
    const c = { ...m, grid: new Uint8Array(m.grid) };
    for (const k of TASKS[m.task].markers) c[k] = { ...m[k] };
    return c;
  }

  // ---------- one run ----------
  class Run {
    // learner: a CWS_LEARN.Learner that lives across runs (the fly's memory); only used when steering = "learned"
    constructor(map, brainData, settings = {}, learner = null) {
      this.map = map;                          // shared with the editor: painting while running changes the world
      this.s = { ...DEFAULTS, ...settings };
      this.learner = learner;
      this.brain = new root.FlyBrain(brainData, { gain: this.s.gain, swapEyes: this.s.wiring === "swapped", seed: this.s.seed });
      this.rng = root.mulberry32(this.s.seed * 7919 + 13);
      this.reset();
    }

    // randomHeading: start facing a random direction (used while training)
    reset(randomHeading = false) {
      const st = this.map.start;
      this.x = st.x; this.y = st.y;
      this.heading = randomHeading ? wrap(this.rng() * 2 * Math.PI) : st.heading || 0;
      this.t = 0;
      this.dnaL = 0; this.dnaR = 0;
      this.eyeL = 0; this.eyeR = 0;
      this.sensL = 0; this.sensR = 0; this.relay = 0;
      this.compassL = 0; this.compassR = 0; this.compassSide = 0;
      this.rays = [];
      this.carrying = false;
      this.phase = this.map.task === "walk" ? "to goal" : "to pickup";
      this.status = "running";                // running | success | timeout
      this.distance = 0; this.bumps = 0; this.bumping = false;
      this.trail = [[this.x, this.y]];
      this.events = [];
      this.pam = 0; this.ppl1 = 0; this.learnL = 0; this.learnR = 0;
      this.brain.reset();
      if (this.learner) this.learner.startEpisode();
    }

    target() {
      if (this.map.task === "walk") return this.map.goal;
      return this.carrying ? this.map.drop : this.map.pickup;
    }

    // how strongly each eye is driven: how much of its field an obstacle fills, weighted by nearness
    // (apparent size ~ 1/distance) and by direction (the frontal part of the eye counts more)
    sense() {
      const s = this.s, fov = (s.eyeFov * Math.PI) / 180, rays = [];
      const eye = [0, 0];
      for (let side = 0; side < 2; side++) {          // 0 = left, 1 = right
        const sign = side === 0 ? -1 : 1;
        let sum = 0, wsum = 0;
        for (let i = 0; i < N_RAYS; i++) {
          const off = ((i + 0.5) / N_RAYS) * fov;
          const ang = this.heading + sign * off;
          const d = castRay(this.map, this.x, this.y, ang, s.eyeRange);
          const loom = d >= s.eyeRange ? 0 : Math.min(1, s.loomNear / Math.max(d, 1e-3));
          const wgt = 1 - 0.6 * (off / fov);
          sum += wgt * loom; wsum += wgt;
          rays.push({ ang, d, side, loom });
        }
        eye[side] = sum / wsum;
      }
      this.rays = rays;
      return eye;
    }

    controlStep() {
      if (this.status !== "running") return;
      const s = this.s, b = this.brain;
      const [lv, rv] = this.sense();
      this.eyeL = s.innate ? s.maxRate * lv : 0;
      this.eyeR = s.innate ? s.maxRate * rv : 0;
      const tg = this.target();

      this.compassL = 0; this.compassR = 0; this.learnL = 0; this.learnR = 0;
      const learning = s.steering === "learned" && this.learner;
      if (s.steering === "compass") {
        // compass: extra drive onto the turning neurons on the side of the current target
        const err = wrap(Math.atan2(tg.y - this.y, tg.x - this.x) - this.heading);
        // target (nearly) straight behind: keep pulling to the same side instead of flipping every step
        if (Math.abs(err) < (5 * Math.PI) / 6 || !this.compassSide) this.compassSide = err >= 0 ? 1 : -1;
        const pull = Math.min(1, Math.abs(err) / (Math.PI / 3)) * s.compass;
        this.compassR = this.compassSide > 0 ? pull : 0;
        this.compassL = this.compassSide < 0 ? pull : 0;
      } else if (learning) {
        this.learner.sense(this);
        [this.learnL, this.learnR] = this.learner.drive();
      }

      b.clearCounts();
      const input = {
        eyeLeft: this.eyeL, eyeRight: this.eyeR,
        dnaLeft: this.compassL + this.learnL + s.spontaneous, dnaRight: this.compassR + this.learnR + s.spontaneous,
      };
      for (let i = 0; i < CONTROL_MS; i++) b.step(input);
      this.dnaL = (1 - SMOOTH) * this.dnaL + SMOOTH * b.rate(b.dnaLeft, CONTROL_MS);
      this.dnaR = (1 - SMOOTH) * this.dnaR + SMOOTH * b.rate(b.dnaRight, CONTROL_MS);
      this.sensL = b.rate(b.sensLeft, CONTROL_MS);
      this.sensR = b.rate(b.sensRight, CONTROL_MS);
      this.relay = b.rate(b.relays, CONTROL_MS);

      const dt = CONTROL_MS / 1000;
      const turn = Math.max(-s.maxTurn, Math.min(s.maxTurn, s.turnGain * (this.dnaR - this.dnaL)));
      this.heading = wrap(this.heading + turn * dt);
      this.turn = turn;

      const speed = s.walkSpeed * (this.carrying ? s.carrySlow : 1);
      const v = speed * dt;
      const nx = this.x + Math.cos(this.heading) * v, ny = this.y + Math.sin(this.heading) * v;
      const ox = this.x, oy = this.y;
      if (!blocked(this.map, nx, ny, FLY_R)) { this.x = nx; this.y = ny; }
      else if (!blocked(this.map, nx, this.y, FLY_R)) this.x = nx;      // slide along the wall
      else if (!blocked(this.map, this.x, ny, FLY_R)) this.y = ny;
      const moved = Math.hypot(this.x - ox, this.y - oy);
      const bumpNow = moved < v * 0.999;
      if (bumpNow && !this.bumping) this.bumps++;
      this.bumping = bumpNow;
      this.distance += moved;
      this.t += dt;
      const last = this.trail[this.trail.length - 1];
      if (Math.hypot(this.x - last[0], this.y - last[1]) > 0.25) this.trail.push([this.x, this.y]);

      const dist = Math.hypot(tg.x - this.x, tg.y - this.y), reached = dist < REACH;
      if (learning) {
        let danger = 0;
        for (const r of this.rays) danger = Math.max(danger, r.loom);
        this.learner.learn(this, { bumped: bumpNow, reached, dist, danger, dt, speed });
      }
      this.pam = learning ? this.learner.pam : 0;
      this.ppl1 = learning ? this.learner.ppl1 : 0;

      if (reached) {
        if (this.map.task === "carry" && !this.carrying) {
          this.carrying = true;
          this.phase = "to drop-off";
          this.events.push({ t: this.t, what: "picked up the load" });
        } else {
          this.status = "success";
          this.phase = "done";
          this.events.push({ t: this.t, what: this.map.task === "walk" ? "reached B" : "delivered the load" });
        }
      } else if (this.t >= s.timeLimit) {
        this.status = "timeout";
        this.events.push({ t: this.t, what: "ran out of time" });
      }
      if (this.status !== "running" && this.learner) this.learner.endEpisode(this);   // every attempt is recorded
    }
  }

  root.CWS = { TASKS, DEFAULTS, CONTROL_MS, FLY_R, REACH, emptyMap, isWall, blocked, lineOfSight, mapToJSON, mapFromJSON, cloneMap, Run };
})(typeof window !== "undefined" ? window : globalThis);
