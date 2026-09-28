// Page logic: two independent instances (Walk A -> B, Carry), each with its own map, fly brain and
// settings; the map painter; drawing of the world and of the brain activity.
(function () {
  "use strict";
  const { TASKS, DEFAULTS, CONTROL_MS, FLY_R, REACH, PRESETS } = CWS;
  const $ = (id) => document.getElementById(id);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const store = {
    get(k) { try { return JSON.parse(localStorage.getItem("cws:" + k)); } catch { return null; } },
    set(k, v) { try { localStorage.setItem("cws:" + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
  };

  // settings shown in the panel: [key, label, min, max, step, note]; "live" ones apply to a running fly
  const SETTINGS = [
    ["walkSpeed", "Walking speed (cells/s)", 0.5, 8, 0.1, "", true],
    ["carrySlow", "Speed while carrying (×)", 0.3, 1, 0.05, "Carry only: the load slows the fly down.", true],
    ["learnRate", "Learning rate", 0, 200, 5, "How much one dopamine burst changes a synapse. 0 = the fly stops learning.", true],
    ["compass", "Compass strength (Hz)", 0, 400, 5, "Fixed compass only: extra input to the turning neuron on the target's side.", true],
    ["spontaneous", "Spontaneous input (Hz)", 0, 150, 5, "Random background input to both turning neurons.", true],
    ["eyeRange", "Eye range (cells)", 2, 15, 0.5, "", true],
    ["loomNear", "Full looming at (cells)", 0.5, 4, 0.1, "An obstacle this close drives its eye fully.", true],
    ["eyeFov", "Each eye's field (degrees)", 40, 170, 5, "", true],
    ["maxRate", "Max eye input (Hz)", 50, 300, 5, "Rate onto each LPLC neuron at full looming.", true],
    ["turnGain", "Turning gain (rad/s per Hz)", 0.01, 0.15, 0.005, "", true],
    ["timeLimit", "Time limit (s)", 20, 600, 10, "", true],
    ["gain", "Synaptic gain (×)", 0.5, 4, 0.1, "One number for every connection. Applies on Reset.", false],
    ["seed", "Random seed", 1, 999, 1, "Same seed + same map = the same run. Applies on Reset.", false],
  ];

  const SELECTS = [
    ["targetSense", "Target sense", [["smell", "smell (senses it through walls)"], ["sight", "sight (only when nothing is in between)"]], "Dopamine learning only.", true],
    ["wiring", "Eye wiring", [["normal", "normal (real wiring)"], ["swapped", "swapped (control: each eye into the wrong side)"]], "Applies on Reset.", false],
  ];
  const CHECKS = [
    ["innate", "Built-in wall avoidance (eyes drive the connectome's LPLC neurons)"],
    ["randomStart", "Random start direction while training"],
  ];
  const { Learner, cueNames, W_MAX } = CWS_LEARN;

  // ---------- instances ----------
  const inst = {};
  for (const task of Object.keys(TASKS)) {
    let map;
    const saved = store.get("map:" + task);
    try { map = saved ? CWS.mapFromJSON(saved) : null; } catch { map = null; }
    if (!map) map = Object.values(PRESETS[task])[0]();
    const settings = { ...DEFAULTS, ...(store.get("settings:" + task) || {}) };
    let learner;
    try { learner = Learner.fromJSON(store.get("memory:" + task), settings.seed); } catch { learner = new Learner(settings.seed); }
    inst[task] = { task, map, settings, learner, run: null, playing: false, training: null, undo: [], trace: [], acc: 0 };
    newRun(inst[task]);
  }
  const view = { showRays: true, showTrail: true, showCompass: true, ...(store.get("view") || {}) };
  let cur = inst[store.get("task") in inst ? store.get("task") : "walk"];
  let tool = "wall";

  function newRun(I) {
    I.run = new CWS.Run(I.map, BRAIN_DATA, I.settings, I.learner);
    I.trace = [];
    I.flash = new Float32Array(BRAIN_DATA.n);
    I.acc = 0;
  }
  function saveMap(I) { store.set("map:" + I.task, CWS.mapToJSON(I.map)); }
  function saveSettings(I) { store.set("settings:" + I.task, I.settings); }
  function saveMemory(I) { store.set("memory:" + I.task, I.learner.toJSON()); }

  // ---------- tabs ----------
  function buildTabs() {
    const nav = $("tabs");
    nav.innerHTML = "";
    for (const [task, t] of Object.entries(TASKS)) {
      const b = document.createElement("button");
      b.textContent = t.label;
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", cur.task === task);
      b.onclick = () => switchTask(task);
      nav.appendChild(b);
    }
  }
  function switchTask(task) {
    if (cur.task === task) return;
    cur.playing = false;
    cur.training = null;
    cur = inst[task];
    store.set("task", task);
    if (!TASKS[task].markers.includes(tool)) tool = "wall";
    buildTabs(); buildTools(); buildPresets(); buildSettings(); buildLearn(); updateButtons(); resize();
  }

  // ---------- tools ----------
  const TOOL_INFO = {
    wall: { label: "Wall", color: "--wall", hint: "Drag to paint walls. Right-drag erases with any tool." },
    erase: { label: "Erase", color: "--floor", hint: "Drag to erase walls." },
    start: { label: "Start (A)", color: "--start", hint: "Click to place the start, drag to set the direction the fly faces." },
    goal: { label: "Goal (B)", color: "--goal", hint: "Click to place B, where the fly has to walk to." },
    pickup: { label: "Pickup", color: "--pickup", hint: "Click to place the load the fly has to fetch." },
    drop: { label: "Drop-off", color: "--drop", hint: "Click to place where the load has to be delivered." },
  };
  function buildTools() {
    const box = $("tools");
    box.innerHTML = "";
    for (const k of ["wall", "erase", ...TASKS[cur.task].markers]) {
      const b = document.createElement("button");
      b.className = "tool";
      b.innerHTML = `<span class="sw" style="background:var(${TOOL_INFO[k].color});${k === "erase" ? "border:1px solid var(--muted)" : ""}"></span>${TOOL_INFO[k].label}`;
      b.setAttribute("aria-pressed", tool === k);
      b.onclick = () => { tool = k; buildTools(); };
      box.appendChild(b);
    }
    $("hint").textContent = TOOL_INFO[tool].hint + "  Keys: Space run/pause, R reset, Ctrl+Z undo.";
  }

  function buildPresets() {
    const sel = $("preset");
    sel.innerHTML = "";
    for (const name of Object.keys(PRESETS[cur.task])) sel.add(new Option(name, name));
  }

  // ---------- settings ----------
  function buildSettings() {
    const box = $("settings");
    box.innerHTML = "";
    const S = cur.settings;
    for (const [key, label, min, max, step, note, live] of SETTINGS) {
      if (key === "carrySlow" && cur.task !== "carry") continue;
      const row = document.createElement("div");
      row.className = "setting";
      row.innerHTML = `<label for="s_${key}">${label}</label><span class="val" id="v_${key}"></span>
        <input type="range" id="s_${key}" min="${min}" max="${max}" step="${step}" value="${S[key]}">
        ${note ? `<span class="note">${note}</span>` : ""}`;
      box.appendChild(row);
      const input = row.querySelector("input"), val = row.querySelector(".val");
      const show = () => { val.textContent = +(+input.value).toFixed(3); };
      show();
      input.oninput = () => {
        S[key] = +input.value;
        show();
        if (live) cur.run.s[key] = S[key];
        saveSettings(cur);
      };
    }
    for (const [key, label, options, note, live] of SELECTS) {
      const row = document.createElement("div");
      row.className = "setting";
      row.innerHTML = `<label for="s_${key}">${label}</label><span></span>
        <select id="s_${key}">${options.map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select>
        <span class="note">${note}</span>`;
      box.appendChild(row);
      const sel = row.querySelector("select");
      sel.value = S[key];
      sel.onchange = () => { S[key] = sel.value; if (live) cur.run.s[key] = S[key]; saveSettings(cur); };
    }
    for (const [key, label] of CHECKS) {
      const l = document.createElement("label");
      l.className = "check";
      l.innerHTML = `<input type="checkbox" ${S[key] ? "checked" : ""}> ${label}`;
      l.querySelector("input").onchange = (e) => { S[key] = e.target.checked ? 1 : 0; cur.run.s[key] = S[key]; saveSettings(cur); };
      box.appendChild(l);
    }
    for (const [key, label] of [["showRays", "Show what the eyes see"], ["showTrail", "Show the path walked"], ["showCompass", "Show the compass target"]]) {
      const l = document.createElement("label");
      l.className = "check";
      l.innerHTML = `<input type="checkbox" ${view[key] ? "checked" : ""}> ${label}`;
      l.querySelector("input").onchange = (e) => { view[key] = e.target.checked; store.set("view", view); };
      box.appendChild(l);
    }
  }
  $("defaults").onclick = () => {
    cur.settings = { ...DEFAULTS };
    saveSettings(cur);
    newRun(cur);
    cur.playing = false;
    cur.training = null;
    buildSettings(); buildLearn(); updateButtons();
  };

  // ---------- run controls ----------
  function updateButtons() {
    $("play").textContent = cur.playing ? "Pause" : cur.run.status === "running" && cur.run.t > 0 ? "Resume" : "Run";
  }
  function togglePlay() {
    cur.training = null;
    if (cur.run.status !== "running") { newRun(cur); }
    cur.playing = !cur.playing;
    updateButtons();
  }
  $("play").onclick = togglePlay;
  $("step").onclick = () => {
    if (cur.run.status !== "running") newRun(cur);
    cur.playing = false;
    cur.training = null;
    stepOnce(cur);
    updateButtons();
  };
  $("reset").onclick = () => { cur.playing = false; cur.training = null; newRun(cur); updateButtons(); };

  function stepOnce(I) {
    const r = I.run;
    r.controlStep();
    const c = r.brain.counts;
    for (let i = 0; i < c.length; i++) if (c[i]) I.flash[i] = 1;
    I.trace.push([r.dnaL, r.dnaR]);
    if (I.trace.length > 300) I.trace.shift();
    if (r.status !== "running") {
      if (r.s.steering === "learned") { saveMemory(I); I.curveDirty = true; }
      const T = I.training;
      if (T && T.done + 1 < T.total) {
        T.done++;
        r.reset(!!I.settings.randomStart);
        I.trace = [];
      } else {
        if (T) T.done = T.total;
        I.training = null;
        I.playing = false;
      }
    }
  }

  // ---------- learning panel ----------
  function buildLearn() {
    const mode = cur.settings.steering;
    for (const b of $("steering").querySelectorAll("button")) {
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", b.dataset.v === mode);
    }
    $("learnBox").hidden = mode !== "learned";
    cur.curveDirty = true;
    buildSynapses();
  }
  for (const b of $("steering").querySelectorAll("button")) {
    b.onclick = () => {
      cur.settings.steering = b.dataset.v;
      cur.run.s.steering = b.dataset.v;
      saveSettings(cur);
      buildLearn();
    };
  }
  $("train").onclick = () => {
    if (cur.training) { cur.training = null; cur.playing = false; updateButtons(); return; }
    const total = +$("trainN").value;
    newRun(cur);
    if (cur.settings.randomStart) cur.run.reset(true);
    cur.training = { total, done: 0 };
    cur.playing = true;
    updateButtons();
  };
  $("forget").onclick = () => {
    if (!confirm("Wipe everything this fly has learned?")) return;
    cur.training = null; cur.playing = false;
    cur.learner.forget(cur.settings.seed);
    saveMemory(cur);
    newRun(cur); buildLearn(); updateButtons();
  };
  $("saveMem").onclick = () => {
    const blob = new Blob([JSON.stringify({ ...cur.learner.toJSON(), task: cur.task })], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${cur.task}-fly-memory.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  $("openMem").onchange = async (e) => {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    try {
      const L = Learner.fromJSON(JSON.parse(await f.text()), cur.settings.seed);
      cur.learner.w.set(L.w);
      cur.learner.episodes = L.episodes;
      saveMemory(cur);
      cur.training = null; cur.playing = false;
      newRun(cur); buildLearn(); updateButtons();
    } catch (err) { alert("Could not open that file: " + err.message); }
  };

  function buildSynapses() {
    const names = cueNames();
    $("synapses").innerHTML = `<div class="syn"><span></span><span class="h">\u2192 left DNa</span><span class="h">\u2192 right DNa</span>` +
      names.map((n) => `<span class="n" title="${n}">${n}</span><span class="c"></span><span class="c"></span>`).join("") + "</div>";
    updateSynapses();
  }
  function updateSynapses() {
    const cells = $("synapses").querySelectorAll(".c"), w = cur.learner.w;
    const cue = cur.settings.steering === "learned" ? cur.learner.cue : null;
    cells.forEach((c, i) => {
      const v = w[i] / W_MAX, active = cue && cue[i >> 1] > 0.2;
      c.style.background = `rgba(242,193,78,${0.08 + 0.85 * v})`;
      c.style.outline = active ? "1px solid #fff" : "none";
      c.textContent = Math.round(w[i]);
    });
  }

  const curveCanvas = $("curve"), cctx = curveCanvas.getContext("2d");
  // one bar per attempt, or per group of attempts once there are too many to fit
  function drawCurve() {
    const I = cur, W = curveCanvas.width, H = curveCanvas.height, dpr = window.devicePixelRatio || 1;
    const eps = I.learner.episodes;
    cctx.fillStyle = css("--floor"); cctx.fillRect(0, 0, W, H);
    const maxBars = Math.max(20, Math.floor(W / (4 * dpr)));
    const per = Math.max(1, Math.ceil(eps.length / maxBars));
    const groups = [];
    for (let i = 0; i < eps.length; i += per) {
      const g = eps.slice(i, i + per);
      groups.push({ t: g.reduce((a, e) => a + e.t, 0) / g.length, ok: g.filter((e) => e.ok).length / g.length, from: i + 1, to: i + g.length });
    }
    const top = 16 * dpr, bottom = 14 * dpr, plotH = H - top - bottom;
    const limit = Math.max(10, ...groups.map((g) => g.t));
    const bw = W / Math.max(groups.length, 20);
    const ok = css("--ok"), bad = css("--bad");
    groups.forEach((g, i) => {
      const h = Math.max(2 * dpr, (g.t / limit) * plotH), x = i * bw + 1, w = Math.max(1, bw - 2);
      cctx.globalAlpha = 0.85;
      cctx.fillStyle = ok;
      cctx.fillRect(x, H - bottom - h, w, h * g.ok);
      cctx.fillStyle = bad;
      cctx.fillRect(x, H - bottom - h + h * g.ok, w, h * (1 - g.ok));
    });
    cctx.globalAlpha = 1;
    if (groups.length > 1) {
      cctx.strokeStyle = "#e6e9ef"; cctx.lineWidth = 1.5 * dpr;
      cctx.beginPath();
      groups.forEach((g, i) => {
        const x = i * bw + bw / 2, y = top + (1 - g.ok) * plotH;
        i ? cctx.lineTo(x, y) : cctx.moveTo(x, y);
      });
      cctx.stroke();
    }
    cctx.fillStyle = css("--muted"); cctx.font = `${10 * dpr}px system-ui, sans-serif`;
    cctx.textAlign = "left";
    cctx.fillText(eps.length ? `longest ${Math.round(limit)} s` : "no attempts yet: press Train or Run", 4 * dpr, 11 * dpr);
    if (eps.length) {
      cctx.fillText("attempt 1", 4 * dpr, H - 3 * dpr);
      cctx.textAlign = "right";
      cctx.fillText(`${eps.length}${per > 1 ? ` (bars of ${per})` : ""}`, W - 4 * dpr, H - 3 * dpr);
      cctx.textAlign = "left";
    }
    const T = I.training, n = I.learner.episodes.length, recent = I.learner.episodes.slice(-50), okN = recent.filter((e) => e.ok).length;
    $("trainInfo").textContent = T
      ? `Training: attempt ${T.done + 1} of ${T.total}\u2026`
      : n ? `${n} attempt${n === 1 ? "" : "s"} so far; last ${recent.length}: ${okN} made it.` : "A new fly: it has not learned anything yet.";
    $("train").textContent = T ? "Stop" : "Train";
  }

  // ---------- map editing ----------
  $("brush").oninput = (e) => { $("brushVal").textContent = e.target.value; };
  function pushUndo() {
    cur.undo.push(CWS.cloneMap(cur.map));
    if (cur.undo.length > 40) cur.undo.shift();
  }
  function replaceMap(I, m) {
    // the run keeps a reference to the map, so copy into the same object
    Object.keys(I.map).forEach((k) => delete I.map[k]);
    Object.assign(I.map, m);
    saveMap(I);
    I.playing = false;
    newRun(I);
    updateButtons();
    resize();
  }
  $("undo").onclick = () => { const m = cur.undo.pop(); if (m) replaceMap(cur, m); };
  $("clear").onclick = () => { pushUndo(); cur.map.grid.fill(0); saveMap(cur); };
  $("border").onclick = () => {
    pushUndo();
    const m = cur.map;
    for (let x = 0; x < m.w; x++) { m.grid[x] = 1; m.grid[(m.h - 1) * m.w + x] = 1; }
    for (let y = 0; y < m.h; y++) { m.grid[y * m.w] = 1; m.grid[y * m.w + m.w - 1] = 1; }
    saveMap(cur);
  };
  $("loadPreset").onclick = () => { pushUndo(); replaceMap(cur, PRESETS[cur.task][$("preset").value]()); };
  $("newMap").onclick = () => {
    pushUndo();
    const [w, h] = $("newSize").value.split("x").map(Number);
    replaceMap(cur, CWS.emptyMap(cur.task, w, h));
  };
  $("saveMap").onclick = () => {
    const blob = new Blob([JSON.stringify(CWS.mapToJSON(cur.map), null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${cur.task}-map.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  $("openMap").onchange = async (e) => {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    try {
      const m = CWS.mapFromJSON(JSON.parse(await f.text()));
      if (m.task !== cur.task) switchTask(m.task);
      pushUndo();
      replaceMap(cur, m);
    } catch (err) { alert("Could not open that file: " + err.message); }
  };

  const canvas = $("map"), ctx = canvas.getContext("2d");
  let cell = 10, painting = null;

  function cellAt(ev) {
    const r = canvas.getBoundingClientRect();
    return { x: ((ev.clientX - r.left) / r.width) * cur.map.w, y: ((ev.clientY - r.top) / r.height) * cur.map.h };
  }
  function paint(p, value) {
    const m = cur.map, size = +$("brush").value, half = (size - 1) / 2;
    const cx0 = Math.round(p.x - 0.5 - half), cy0 = Math.round(p.y - 0.5 - half);
    for (let y = cy0; y < cy0 + size; y++) for (let x = cx0; x < cx0 + size; x++) {
      if (x < 0 || y < 0 || x >= m.w || y >= m.h) continue;
      if (value && overlapsFly(x, y)) continue;   // never bury the fly inside a wall
      m.grid[y * m.w + x] = value;
    }
  }
  function overlapsFly(cx, cy) {
    const r = cur.run, nx = Math.max(cx, Math.min(r.x, cx + 1)), ny = Math.max(cy, Math.min(r.y, cy + 1));
    return (nx - r.x) ** 2 + (ny - r.y) ** 2 < FLY_R * FLY_R;
  }
  function paintLine(a, b, value) {
    const n = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) * 2));
    for (let i = 0; i <= n; i++) paint({ x: a.x + ((b.x - a.x) * i) / n, y: a.y + ((b.y - a.y) * i) / n }, value);
  }
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    const p = cellAt(e);
    pushUndo();
    const t = e.button === 2 ? "erase" : tool;
    if (t === "wall" || t === "erase") {
      painting = { kind: "paint", value: t === "wall" ? 1 : 0, last: p };
      paint(p, painting.value);
    } else {
      painting = { kind: "marker", key: t, from: p };
      const cx = Math.floor(p.x) + 0.5, cy = Math.floor(p.y) + 0.5;
      cur.map[t] = t === "start" ? { x: cx, y: cy, heading: cur.map.start.heading || 0 } : { x: cx, y: cy };
      cur.map.grid[Math.floor(cy) * cur.map.w + Math.floor(cx)] = 0;
      if (t === "start" && !cur.playing && (cur.run.t === 0 || cur.run.status !== "running")) newRun(cur);
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    const p = cellAt(e);
    hover = p;
    if (!painting) return;
    if (painting.kind === "paint") { paintLine(painting.last, p, painting.value); painting.last = p; }
    else if (painting.key === "start") {
      const s = cur.map.start, dx = p.x - s.x, dy = p.y - s.y;
      if (Math.hypot(dx, dy) > 0.6) {
        s.heading = Math.atan2(dy, dx);
        if (!cur.playing && (cur.run.t === 0 || cur.run.status !== "running")) newRun(cur);
      }
    }
  });
  const endPaint = () => { if (painting) { painting = null; saveMap(cur); } };
  canvas.addEventListener("pointerup", endPaint);
  canvas.addEventListener("pointercancel", endPaint);
  let hover = null;
  canvas.addEventListener("pointerleave", () => { hover = null; });

  window.addEventListener("keydown", (e) => {
    if (e.target.closest("input, select, textarea")) return;
    if (e.code === "Space") { e.preventDefault(); togglePlay(); }
    else if (e.key === "r" || e.key === "R") $("reset").click();
    else if ((e.ctrlKey || e.metaKey) && e.key === "z") { e.preventDefault(); $("undo").click(); }
  });

  // ---------- drawing: map ----------
  function resize() {
    const wrap = $("mapWrap"), m = cur.map;
    const availW = wrap.clientWidth - 16;
    const availH = Math.max(260, window.innerHeight - 230);
    cell = Math.max(4, Math.min(availW / m.w, availH / m.h));
    const dpr = window.devicePixelRatio || 1;
    canvas.style.width = `${cell * m.w}px`;
    canvas.style.height = `${cell * m.h}px`;
    canvas.width = Math.round(cell * m.w * dpr);
    canvas.height = Math.round(cell * m.h * dpr);
    ctx.setTransform((canvas.width / m.w), 0, 0, (canvas.height / m.h), 0, 0);   // draw in cell units
    for (const c of [brainCanvas, traceCanvas, curveCanvas]) {
      c.width = Math.round(c.clientWidth * dpr);
      c.height = Math.round(c.clientHeight * dpr);
    }
  }
  window.addEventListener("resize", resize);

  function drawMarker(p, color, label, ring) {
    ctx.save();
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.18;
    ctx.beginPath(); ctx.arc(p.x, p.y, REACH, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1;
    if (ring) { ctx.setLineDash([0.25, 0.2]); ctx.lineWidth = 0.08; ctx.strokeStyle = color; ctx.stroke(); ctx.setLineDash([]); }
    ctx.beginPath(); ctx.arc(p.x, p.y, 0.42, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#0b0d11";
    ctx.font = "bold 0.5px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(label, p.x, p.y + 0.02);
    ctx.restore();
  }

  function drawFly(r) {
    ctx.save();
    ctx.translate(r.x, r.y);
    ctx.rotate(r.heading);
    ctx.fillStyle = "rgba(200,220,255,0.35)";            // wings
    ctx.beginPath(); ctx.ellipse(-0.12, -0.24, 0.32, 0.13, -0.5, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(-0.12, 0.24, 0.32, 0.13, 0.5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#e0b04a";                            // body
    ctx.beginPath(); ctx.ellipse(-0.05, 0, 0.3, 0.14, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#c0392b";                            // head / eyes
    ctx.beginPath(); ctx.arc(0.26, -0.07, 0.07, 0, Math.PI * 2); ctx.arc(0.26, 0.07, 0.07, 0, Math.PI * 2); ctx.fill();
    if (r.carrying) {
      ctx.fillStyle = css("--pickup");
      ctx.strokeStyle = "#0b0d11"; ctx.lineWidth = 0.04;
      ctx.fillRect(-0.3, -0.16, 0.32, 0.32); ctx.strokeRect(-0.3, -0.16, 0.32, 0.32);
    }
    ctx.restore();
  }

  function drawMap() {
    const I = cur, m = I.map, r = I.run;
    ctx.fillStyle = css("--floor");
    ctx.fillRect(0, 0, m.w, m.h);
    if (cell >= 7) {
      ctx.strokeStyle = css("--grid"); ctx.lineWidth = 1 / cell;
      ctx.beginPath();
      for (let x = 1; x < m.w; x++) { ctx.moveTo(x, 0); ctx.lineTo(x, m.h); }
      for (let y = 1; y < m.h; y++) { ctx.moveTo(0, y); ctx.lineTo(m.w, y); }
      ctx.stroke();
    }
    ctx.fillStyle = css("--wall");
    for (let y = 0; y < m.h; y++) for (let x = 0; x < m.w; x++) if (m.grid[y * m.w + x]) ctx.fillRect(x, y, 1.02, 1.02);

    if (view.showTrail && r.trail.length > 1) {
      ctx.strokeStyle = "rgba(242,193,78,0.45)"; ctx.lineWidth = 0.08; ctx.lineJoin = "round";
      ctx.beginPath();
      r.trail.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.lineTo(r.x, r.y);
      ctx.stroke();
    }

    // markers
    const st = m.start;
    drawMarker(st, css("--start"), "A", false);
    ctx.save();
    ctx.strokeStyle = css("--start"); ctx.lineWidth = 0.1;
    ctx.beginPath(); ctx.moveTo(st.x + Math.cos(st.heading) * 0.5, st.y + Math.sin(st.heading) * 0.5);
    ctx.lineTo(st.x + Math.cos(st.heading) * 1.2, st.y + Math.sin(st.heading) * 1.2); ctx.stroke();
    ctx.restore();
    if (m.task === "walk") drawMarker(m.goal, css("--goal"), "B", true);
    else {
      drawMarker(m.drop, css("--drop"), "D", true);
      if (!r.carrying && r.status !== "success") {
        ctx.fillStyle = css("--pickup");
        ctx.fillRect(m.pickup.x - 0.35, m.pickup.y - 0.35, 0.7, 0.7);
        ctx.strokeStyle = css("--pickup"); ctx.lineWidth = 0.06; ctx.setLineDash([0.2, 0.15]);
        ctx.beginPath(); ctx.arc(m.pickup.x, m.pickup.y, REACH, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
      } else if (r.status === "success") {
        ctx.fillStyle = css("--pickup");
        ctx.fillRect(m.drop.x - 0.3, m.drop.y + 0.1, 0.5, 0.5);
      }
    }

    // eyes
    if (view.showRays && r.rays.length) {
      ctx.lineWidth = 0.05;
      for (const ray of r.rays) {
        const col = ray.side === 0 ? "63,200,192" : "239,111,154";
        ctx.strokeStyle = `rgba(${col},${0.08 + 0.6 * ray.loom})`;
        ctx.beginPath(); ctx.moveTo(r.x, r.y);
        ctx.lineTo(r.x + Math.cos(ray.ang) * ray.d, r.y + Math.sin(ray.ang) * ray.d); ctx.stroke();
      }
    }
    if (view.showCompass && r.status === "running") {
      const tg = r.target();
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.18)"; ctx.lineWidth = 0.05; ctx.setLineDash([0.3, 0.3]);
      ctx.beginPath(); ctx.moveTo(r.x, r.y); ctx.lineTo(tg.x, tg.y); ctx.stroke();
      ctx.restore();
    }
    drawFly(r);

    if (hover && !painting && (tool === "wall" || tool === "erase")) {
      const size = +$("brush").value, half = (size - 1) / 2;
      ctx.strokeStyle = "rgba(242,193,78,0.7)"; ctx.lineWidth = 1.5 / cell;
      ctx.strokeRect(Math.round(hover.x - 0.5 - half), Math.round(hover.y - 0.5 - half), size, size);
    }
  }

  // ---------- drawing: brain ----------
  const brainCanvas = $("brain"), bctx = brainCanvas.getContext("2d");
  const traceCanvas = $("trace"), tctx = traceCanvas.getContext("2d");
  const B = BRAIN_DATA;
  // frame the bulk of the neurons (2nd..98th percentile); the few far-away cell bodies are pulled to the edge
  const bounds = (() => {
    const q = (arr, f) => { const a = [...arr].sort((u, v) => u - v); return a[Math.floor(f * (a.length - 1))]; };
    const xs = B.pos.map((p) => p[0]), ys = B.pos.map((p) => p[1]);
    return { x0: q(xs, 0.02), x1: q(xs, 0.98), y0: q(ys, 0.02), y1: q(ys, 0.98) };
  })();
  // each LPLC neuron is coloured by the eye it listens to in the current run
  function eyeOf(I, i) {
    const b = I.run.brain;
    if (!I._eyeMap || I._eyeMapFor !== b) {
      I._eyeMap = new Int8Array(B.n);
      b.sensLeft.forEach((k) => (I._eyeMap[k] = -1));
      b.sensRight.forEach((k) => (I._eyeMap[k] = 1));
      I._eyeMapFor = b;
    }
    return I._eyeMap[i];
  }

  function drawBrain(dtReal) {
    const I = cur, W = brainCanvas.width, H = brainCanvas.height, pad = 14 * (window.devicePixelRatio || 1);
    bctx.fillStyle = css("--floor"); bctx.fillRect(0, 0, W, H);
    const sx = (W - 2 * pad) / (bounds.x1 - bounds.x0), sy = (H - 2 * pad) / (bounds.y1 - bounds.y0);
    const s = Math.min(sx, sy);
    const ox = (W - (bounds.x1 - bounds.x0) * s) / 2, oy = (H - (bounds.y1 - bounds.y0) * s) / 2;
    const cl = (v, a, b) => Math.max(a, Math.min(b, v));
    const px = (x) => ox + (cl(x, bounds.x0, bounds.x1) - bounds.x0) * s, py = (y) => H - (oy + (cl(y, bounds.y0, bounds.y1) - bounds.y0) * s);
    const decay = Math.exp(-dtReal / 0.12);
    const colors = { L: css("--eye-l"), R: css("--eye-r"), relay: css("--relay"), dna: css("--accent") };
    const dpr = window.devicePixelRatio || 1;
    for (let i = 0; i < B.n; i++) {
      const role = B.role[i];
      const f = I.flash[i];
      I.flash[i] *= decay;
      const base = role === 0 ? (eyeOf(I, i) < 0 ? colors.L : colors.R) : role === 1 ? colors.relay : colors.dna;
      const rad = (role === 2 ? 4.5 : 1.6) * dpr;
      bctx.globalAlpha = role === 2 ? 1 : 0.35 + 0.65 * f;
      bctx.fillStyle = f > 0.5 ? "#ffffff" : base;
      bctx.beginPath(); bctx.arc(px(B.pos[i][0]), py(B.pos[i][1]), rad + (f > 0.5 ? dpr : 0), 0, Math.PI * 2); bctx.fill();
    }
    bctx.globalAlpha = 1;
    bctx.fillStyle = css("--muted");
    bctx.font = `${11 * dpr}px system-ui, sans-serif`;
    bctx.textAlign = "left"; bctx.fillText("fly's left", 6 * dpr, H - 6 * dpr);
    bctx.textAlign = "right"; bctx.fillText("fly's right", W - 6 * dpr, H - 6 * dpr);
  }

  function drawTrace() {
    const I = cur, W = traceCanvas.width, H = traceCanvas.height, dpr = window.devicePixelRatio || 1;
    tctx.fillStyle = css("--floor"); tctx.fillRect(0, 0, W, H);
    const maxHz = Math.max(40, ...I.trace.map(([a, b]) => Math.max(a, b)));
    const n = 300;
    for (const [k, col] of [[0, css("--eye-l")], [1, css("--eye-r")]]) {
      tctx.strokeStyle = col; tctx.lineWidth = 1.5 * dpr;
      tctx.beginPath();
      I.trace.forEach((v, i) => {
        const x = W - ((I.trace.length - 1 - i) / (n - 1)) * W, y = H - 3 * dpr - (v[k] / maxHz) * (H - 8 * dpr);
        i ? tctx.lineTo(x, y) : tctx.moveTo(x, y);
      });
      tctx.stroke();
    }
    tctx.fillStyle = css("--muted"); tctx.font = `${10 * dpr}px system-ui, sans-serif`;
    tctx.fillText(`${Math.round(maxHz)} Hz`, 4 * dpr, 12 * dpr);
  }

  const METERS = [
    ["Eye input", (r) => [r.eyeL, r.eyeR], 300],
    ["LPLC firing", (r) => [r.sensL, r.sensR], 80],
    ["Target drive", (r) => [r.compassL + r.learnL, r.compassR + r.learnR], 400],
    ["DNa (turning)", (r) => [r.dnaL, r.dnaR], 100],
  ];
  function buildMeters() {
    const box = $("meters");
    box.innerHTML = `<span></span><span class="head">left</span><span class="head">right</span>`;
    for (const [name] of METERS) {
      box.insertAdjacentHTML("beforeend", `<span class="name">${name}</span><div class="bar l"><i></i><span></span></div><div class="bar r"><i></i><span></span></div>`);
    }
  }
  function updateMeters() {
    const bars = $("meters").querySelectorAll(".bar");
    METERS.forEach(([, get, max], k) => {
      const v = get(cur.run);
      for (let s = 0; s < 2; s++) {
        const bar = bars[k * 2 + s];
        bar.firstChild.style.width = `${Math.min(100, (v[s] / max) * 100)}%`;
        bar.lastChild.textContent = `${Math.round(v[s])} Hz`;
      }
    });
  }

  function updateStats() {
    const r = cur.run;
    const st = $("stStatus");
    st.textContent = r.status === "running" ? (cur.playing ? "running" : r.t > 0 ? "paused" : "ready") : r.status === "success" ? "success" : "out of time";
    st.className = r.status;
    $("stPhase").textContent = r.phase;
    $("stTime").textContent = `${r.t.toFixed(1)} s`;
    $("stDist").textContent = `${r.distance.toFixed(1)} cells`;
    $("stBumps").textContent = r.bumps;
    const ev = $("events");
    if (ev.childElementCount !== r.events.length || ev._run !== r) {
      ev._run = r;
      ev.innerHTML = r.events.map((e) => `<li>${e.t.toFixed(1)} s: ${e.what}</li>`).join("");
    }
    const banner = $("banner");
    if (r.status === "success") {
      banner.hidden = false; banner.className = "banner ok";
      banner.textContent = (cur.task === "walk" ? "Reached B" : "Delivered") + ` in ${r.t.toFixed(1)} s, ${r.bumps} bump${r.bumps === 1 ? "" : "s"}`;
    } else if (r.status === "timeout") {
      banner.hidden = false; banner.className = "banner bad";
      banner.textContent = `Out of time after ${r.t.toFixed(0)} s` + (cur.task === "carry" && r.carrying ? " (was carrying the load)" : "");
    } else banner.hidden = true;
  }

  // ---------- main loop ----------
  let lastT = performance.now(), wasPlaying = false, synTick = 0;
  const dopa = { pam: 0, ppl1: 0 };
  function updateDopamine(dtReal) {
    // hold each burst on screen for a moment so it can be seen at any speed
    const r = cur.run, k = Math.exp(-dtReal / 0.35);
    dopa.pam = Math.max(dopa.pam * k, Math.min(1, r.pam / 2));
    dopa.ppl1 = Math.max(dopa.ppl1 * k, Math.min(1, r.ppl1 / 2));
    document.querySelector(".bar.pam i").style.width = `${dopa.pam * 100}%`;
    document.querySelector(".bar.ppl1 i").style.width = `${dopa.ppl1 * 100}%`;
  }
  function frame(now) {
    const dtReal = Math.min(0.1, (now - lastT) / 1000);
    lastT = now;
    const I = cur;
    if (I.playing && I.training) {
      const budgetEnd = performance.now() + 40;   // train as fast as the computer allows
      while (I.playing && performance.now() < budgetEnd) stepOnce(I);
    } else if (I.playing) {
      I.acc += dtReal * +$("speed").value;
      const stepDt = CONTROL_MS / 1000, budgetEnd = performance.now() + 40;
      while (I.acc >= stepDt && I.playing && performance.now() < budgetEnd) { stepOnce(I); I.acc -= stepDt; }
      if (I.acc > Math.max(0.5, 0.1 * +$("speed").value)) I.acc = 0;   // the computer can't keep up with this speed: don't pile up a backlog
    }
    if (wasPlaying !== I.playing) { updateButtons(); wasPlaying = I.playing; }
    drawMap();
    drawBrain(dtReal);
    drawTrace();
    updateMeters();
    updateStats();
    updateDopamine(dtReal);
    if (I.curveDirty) { drawCurve(); I.curveDirty = false; }
    if ((synTick += dtReal) > 0.2) { synTick = 0; updateSynapses(); }
    requestAnimationFrame(frame);
  }

  buildTabs(); buildTools(); buildPresets(); buildSettings(); buildMeters(); buildLearn(); updateButtons();
  resize();
  requestAnimationFrame(frame);
})();
