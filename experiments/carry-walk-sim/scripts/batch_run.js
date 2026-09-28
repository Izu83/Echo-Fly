// Run the simulation without the browser, many times, and print how often the fly succeeds.
//
//   node scripts/batch_run.js                         every built-in map, 10 runs each (dopamine learning)
//   node scripts/batch_run.js --train 20              first train each fly for 20 attempts, then test it
//   node scripts/batch_run.js --steering compass      the fixed compass instead of learning
//   node scripts/batch_run.js --learnRate 0           a fly that cannot learn (stays naive)
//   node scripts/batch_run.js --map my_map.json       a map saved from the page ("Save map")
//   node scripts/batch_run.js --wiring swapped        control: each eye wired into the other side
//
// Any setting of the page can be given the same way: --walkSpeed 4 --innate 0 --targetSense sight ...
// With dopamine learning, one fly is used per map and keeps learning through all its attempts
// (training attempts start facing a random direction; test runs start as the map says).
"use strict";
const fs = require("fs");
const path = require("path");

const WEB = path.join(__dirname, "..", "web");
for (const f of ["brain_data.js", "brain.js", "sim.js", "presets.js", "learning.js"]) require(path.join(WEB, f));
const { CWS, CWS_LEARN, BRAIN_DATA } = globalThis;

const args = process.argv.slice(2);
const opt = { runs: 10, train: 0 };
const settings = {};
for (let i = 0; i < args.length; i += 2) {
  const k = args[i].replace(/^--/, ""), v = args[i + 1];
  if (k === "runs" || k === "train") opt[k] = +v;
  else if (k === "map") opt.map = v;
  else if (k in CWS.DEFAULTS) settings[k] = isNaN(+v) ? v : +v;
  else { console.error(`unknown option --${k}`); process.exit(1); }
}

const maps = [];
if (opt.map) maps.push([path.basename(opt.map), CWS.mapFromJSON(JSON.parse(fs.readFileSync(opt.map, "utf8")))]);
else for (const task of Object.keys(CWS.PRESETS)) for (const [name, fn] of Object.entries(CWS.PRESETS[task])) maps.push([`${task} / ${name}`, fn()]);

const S = { ...CWS.DEFAULTS, ...settings };
console.log(`settings: ${JSON.stringify({ ...S, seed: "1.." + opt.runs, train: opt.train })}\n`);
console.log("map".padEnd(34) + "success   mean time   mean bumps   picked up");
for (const [name, map] of maps) {
  const learner = S.steering === "learned" ? new CWS_LEARN.Learner(1) : null;
  if (learner && opt.train) {
    const run = new CWS.Run(map, BRAIN_DATA, { ...settings, seed: 1000 }, learner);
    for (let e = 0; e < opt.train; e++) {
      run.reset(!!S.randomStart);
      while (run.status === "running") run.controlStep();
    }
  }
  let ok = 0, time = 0, bumps = 0, picked = 0;
  for (let seed = 1; seed <= opt.runs; seed++) {
    const run = new CWS.Run(map, BRAIN_DATA, { ...settings, seed }, learner);
    while (run.status === "running") run.controlStep();
    if (run.status === "success") { ok++; time += run.t; }
    bumps += run.bumps;
    if (run.carrying || (map.task === "carry" && run.status === "success")) picked++;
  }
  const pick = map.task === "carry" ? `${picked}/${opt.runs}` : "-";
  console.log(
    name.padEnd(34) + `${ok}/${opt.runs}`.padEnd(10) +
    (ok ? (time / ok).toFixed(1) + " s" : "-").padEnd(12) + (bumps / opt.runs).toFixed(1).padEnd(13) + pick
  );
}
