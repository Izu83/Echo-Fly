# Carry-Walk Sim: a fly brain walking a map you paint

A 2D world where a simulated fly walks on its own. The fly always walks forward. Only a spiking circuit cut
from the real **male CNS connectome** (Janelia FlyEM, CC-BY) decides where it turns. That circuit is the same
one as in [`wall-dodge`](../wall-dodge/): looming neurons, relay neurons, turning neurons.

There are two separate uses of the fly brain. Each one is its own instance, with its own map, its own brain
and its own settings:

| Tab | The fly has to... |
|---|---|
| **Walk A → B** | walk from the start **A** to the goal **B** |
| **Carry** | walk to the **pickup**, take the load (which slows it down), and carry it to the **drop-off** |

You paint the maps yourself: walls, erasing, start (with the direction the fly faces), goal, pickup and
drop-off. You can also start from a ready-made map, and save or open your maps as `.json` files.

The fly **learns** how to reach its target through **dopamine**. A new fly has no idea where to go. Reward
neurons (PAM) fire when things go better than expected, and punishment neurons (PPL1) fire when it bumps into
a wall or a wall looms up. Over a few attempts it works out which way to turn. See
[Dopamine learning](#dopamine-learning).

## Start

Double-click **`run.bat`**, or open **`web/index.html`** in a browser. It works offline and needs no install.

1. Pick a tab: **Walk A → B** or **Carry**.
2. Paint a map, or pick one from the list under the map and press **Load**.
3. Press **Train** to let the fly practise, from 10 up to 1000 attempts, at full speed. The learning curve
   shows the time each attempt took (green = made it, red = failed) and the success rate. With many attempts,
   each bar is a group of attempts. **Forget** wipes what it has learned.
4. Press **Run** (or Space) to watch one attempt. Use **Speed** to go faster, and **Reset** (or R) to start over.

**Painting**

| Tool | What it does |
|---|---|
| Wall / Erase | Drag to paint or erase walls. Right-drag always erases. The **Brush** slider sets the brush size. |
| Start (A) | Click to place the start. Drag from it to set the direction the fly faces. |
| Goal (B) / Pickup / Drop-off | Click to place the marker. |
| Undo (Ctrl+Z), Clear, Border | Undo the last change, remove every wall, or add walls around the edge. |
| New empty map | Start from a blank map: 48 × 30, 64 × 40 or 96 × 60 cells. |
| Save map / Open map | Download the map as `.json`, or load one back. |

You can paint while the fly is running, for example to drop a wall in front of it. Each tab remembers its
own map and settings in the browser between visits.

## How the fly works

```
 eyes (ray casting)          male CNS sub-circuit, 820 spiking neurons            body
 ------------------   ------------------------------------------------------   ---------------------
 left eye  looming --> 210 LPLC1/2/4 --\                                        turning speed =
                                        >-- 400 relays --> DNa01 + DNa02 L/R --> gain x (right - left)
 right eye looming --> 206 LPLC1/2/4 --/                    ^                   forward speed fixed
                                                            |
 8 target-direction cells + 6 wall cells ==[plastic]========+  learning layer (dopamine), or a fixed compass
                                              ^        ^
                                   PAM (reward)        PPL1 (punishment)
```

1. **Eyes.** Each eye looks from straight ahead out to its own side (100° by default), with 11 rays. Every ray
   that hits a wall adds looming. Looming grows like the wall's apparent size (about 1/distance), and the
   frontal part of the eye counts more. The eye's value, from 0 to 1, becomes a Poisson input rate of up to
   150 Hz onto every LPLC neuron of that eye (the same scale as wall-dodge).
2. **Brain.** 416 LPLC neurons, 400 relays and the 4 turning neurons, joined by their 54k real connections
   (336k synapses). Each connection's sign comes from the predicted neurotransmitter. The neurons are leaky
   integrate-and-fire units with 1 ms steps, the same model and the same global gain of 2 as wall-dodge
   (`web/brain.js` is a port of `wall-dodge/scripts/brain.py`). No line of code says "turn away from walls".
   That behaviour comes out of the wiring.
3. **Turning.** Every 20 ms the rates of the left and right DNa neurons are read out, and the fly turns at
   `0.06 rad/s × (right − left)`, at most 5 rad/s. Forward speed is fixed (3 cells/s, times 0.75 while carrying).
   A fly that walks into a wall slides along it and the bump is counted.
4. **Finding the target.** This piece of the brain only sees looming. It has no idea where B, the pickup
   or the drop-off is. There are three options under **Finding the target**:
   - **Dopamine learning** (the default): the fly learns it, see below.
   - **Fixed compass**: a hand-made stand-in for the fly's navigation centre (the central complex, not in this
     circuit). It sends extra input (up to 200 Hz) to the turning neuron on the side of the target.
   - **None**: only the connectome's wall avoidance.

   Either way, the connectome decides whether that extra input wins. When an eye sees a wall close by, the
   looming pathway silences the opposite turning neuron, so avoiding the wall comes first.
5. **Spontaneous input.** Both turning neurons also get a small random input (60 Hz), so the fly wobbles a
   little and never freezes in a perfectly symmetric spot.

**Brain panel.** It shows the 820 neurons where their cell bodies sit (fly seen from behind), flashing white
when they fire. Below that are meters for the eye input, LPLC firing, compass and DNa rates, and a 6-second
trace of the left and right turning neurons.

## Dopamine learning

The fly has **14 sense cells** that feed the turning neurons through **plastic synapses**:

- **8 target-direction cells**, 45° apart. A cell fires when the current target (B, the pickup, or the
  drop-off once it carries the load) lies in its direction. With *Target sense = smell* the fly senses it
  through walls. With *sight* it only senses it when nothing is in between.
- **6 wall cells**: the front, middle and side part of each eye, driven by how close walls are.

A new fly starts with small random synapses, so it has no preference. Then, every 20 ms:

1. **Tag.** A synapse gets tagged when its cell was active and the fly turned toward that synapse's side, and
   tagged negatively when the fly turned the other way. Tags fade over ~0.6 s.
2. **Dopamine.** The fly compares how things are going with how they usually go (reward prediction error):
   - **PAM (reward)** fires when it is better than expected: getting closer to the target, a wall moving
     away. It fires a big burst when the fly grabs the load or arrives.
   - **PPL1 (punishment)** fires when it is worse: walking away from the target, a wall looming up. It fires a
     burst on every bump into a wall.
3. **Two compartments.** As in the mushroom body, each dopamine signal only reaches its own synapses:
   - The **target** signal (getting closer, walking away, arriving) only teaches the target-direction synapses.
   - The **wall** signal (a wall looming up or moving away, bumps) only teaches the wall synapses.

   Without this split, a map like *Two rooms*, where the fly has to walk away from B to find the door, made
   the "walking away" punishment wipe out its wall knowledge and the bumps wipe out its target knowledge.
   Training fell apart after a while.
4. **Learn.** Each synapse changes by `learning rate × (PAM − PPL1 of its compartment) × tag`, and stays
   between 0 and 200 Hz.

So a turn that was followed by good news happens more often in that situation, and a turn followed by a bump
happens less. The fly learns "target on my right → turn right" and, with the built-in wall avoidance switched
off, also "wall on my left → turn right". What it learned stays between attempts, is kept in the browser, and
can be saved as a *memory* file. The **What it has learned** table shows every synapse; the cells active right
now are outlined.

**Where this comes from.** In real flies, learning happens in the mushroom body. There, PAM dopamine neurons
signal reward, PPL1 dopamine neurons signal punishment, and dopamine changes the synapses that were just
active. This is called a three-factor rule. The sense cells and plastic synapses here are a model of that idea.
They are **not** neurons from the connectome: only the 820-neuron looming circuit is.

## Results so far

**Dopamine learning.** 10 test runs per map from the map's start, with one fly per map. The *naive* fly has
learning switched off (`--learnRate 0`). The *trained* fly practised 10 attempts first (`--train 10`), facing a
random direction each time. The last column trained 20 attempts **without the built-in wall avoidance**
(`--train 20 --innate 0`), so all of its wall avoidance was learned from punishment.

| Map | Naive (can't learn) | Trained 10 attempts | Trained 20, no built-in wall avoidance |
|---|---|---|---|
| Walk: Open room | 10/10 (46 s) | 10/10 (20 s) | 10/10 (19 s) |
| Walk: Pillars | 10/10 (60 s) | 10/10 (20 s) | 10/10 (21 s, 1.8 bumps) |
| Walk: Wall in the way | 6/10 (71 s) | 10/10 (19 s) | 10/10 (21 s) |
| Walk: Two rooms | 0/10 | 10/10 (31 s) | 7/10 (30 s, 4.9 bumps) |
| Walk: Zigzag | 10/10 (72 s) | 10/10 (54 s) | 1/10 |
| Carry: Open floor | 0/10 | 10/10 (34 s) | 10/10 (34 s) |
| Carry: Warehouse | 0/10 | 10/10 (41 s) | 10/10 (55 s, 7.8 bumps) |
| Carry: Fetch from next room | 0/10 | 10/10 (53 s) | 2/10 |
| Carry: Pillar field | 3/10 (100 s) | 10/10 (49 s) | 6/10 (54 s) |
| **Total** | **39/90** | **90/90** | **66/90** |

- **Learning works.** After 10 practice attempts the fly makes it every time, on every map, with about one bump
  or fewer per run. It is faster than the fixed compass on *Wall in the way* (19 s vs 39 s), *Zigzag* (54 s vs
  72 s) and *Fetch from next room* (53 s vs 101 s).
- **The naive fly** only makes it when its random start happens to point roughly the right way, or when it
  bumbles into the target. It almost never manages the carry tasks, which need two targets.
- **Walls learned from scratch.** Without the built-in wall avoidance, the fly learns to avoid walls from
  punishment alone and succeeds 66/90. It bumps much more. Maps where it has to walk away from the target to get
  around a wall (*Zigzag*, *Fetch from next room*) are mostly too hard.
- **Long training stays stable.** One fly per map trained for 300 attempts kept succeeding throughout (Zigzag
  and Fetch from next room dipped to 90–95% for a few attempts). The graphs are in [`output/graphs/`](output/graphs/).

**Fixed compass and checks.** `node scripts/batch_run.js --steering compass` runs every ready-made map 10
times (seeds 1 to 10). The two checks change one thing each: **swapped** wires each eye into the wrong side
of the brain, and **no compass** (`--steering none`) leaves only the connectome steering.

| Map | Fixed compass, real wiring | Swapped eyes (check) | No compass (check) |
|---|---|---|---|
| Walk: Open room | 10/10 (17 s) | 10/10 | 6/10 |
| Walk: Pillars | 10/10 (20 s) | 0/10 | 2/10 |
| Walk: Wall in the way | 10/10 (39 s) | 0/10 | 5/10 |
| Walk: Two rooms | 10/10 (36 s) | 0/10 | 2/10 |
| Walk: Zigzag | 10/10 (72 s) | 0/10 | 0/10 |
| Carry: Open floor | 10/10 (28 s) | 10/10 | 0/10 |
| Carry: Warehouse | 10/10 (35 s) | 0/10 | 0/10 |
| Carry: Fetch from next room | 10/10 (101 s) | 0/10 | 0/10 |
| Carry: Pillar field | 10/10 (45 s) | 0/10 | 1/10 |

What this says:

- **The looming wiring does the obstacle avoidance.** With the eyes swapped, the fly steers into walls and
  gets stuck at the first one. It only succeeds on the two maps with nothing in the way.
- **The compass (or learning) supplies the direction.** Without it the fly avoids walls but wanders, and
  reaches a target only by chance.

**Caveats.**
- The compass, the sense cells and the plastic synapses are not from the connectome. The dopamine rule is a
  simple model of mushroom-body learning, not a simulation of the real mushroom body.
- The tuning numbers (eye model, compass strength, turning gain, learning rate, the 200 Hz synapse ceiling)
  were chosen by hand so that the ready-made maps work.
- The fly always senses which direction its target is in (by smell, or by sight if you choose that).
  What it has to learn is what to do with that information.
- The circuit is ~800 of ~200k neurons, which is why it needs the synaptic gain of 2.
- A reactive fly like this one can still get trapped in dead ends that point toward the target, for example a
  U-shaped wall. It has no memory of where it has been.

## Files

```
carry-walk-sim/
  run.bat                 opens the simulation (Windows)
  web/
    index.html            the page: map painter, both tasks, brain view
    app.js                page logic, painting, drawing
    sim.js                the 2D world, the eyes, one run of the fly (tasks, pickup, drop-off)
    brain.js              the spiking circuit (leaky integrate-and-fire, 1 ms steps)
    presets.js            ready-made maps
    learning.js           dopamine learning: sense cells, plastic synapses, PAM / PPL1, the learning rule
    brain_data.js         the 820-neuron circuit from the connectome (generated, see below)
    charts.js             the charts on the page (success rate, time, bumps, what it learned, dopamine)
    style.css
  output/graphs/          charts of the results: learning over 300 attempts, naive vs trained
  output/gifs/            short recordings of the fly walking, carrying, and before vs after learning
  scripts/
    export_brain.py       rebuilds web/brain_data.js from wall-dodge's subnetwork.npz
    batch_run.js          runs maps many times without the browser and prints success rates
```

**Batch runs** (needs [Node.js](https://nodejs.org)):

```bash
node scripts/batch_run.js                          # every ready-made map, 10 runs each (learning fly)
node scripts/batch_run.js --train 10               # practise 10 attempts per map first, then test
node scripts/batch_run.js --learnRate 0            # a naive fly that cannot learn
node scripts/batch_run.js --steering compass       # the fixed compass instead of learning
node scripts/batch_run.js --map walk-map.json      # your own map, saved with "Save map"
node scripts/batch_run.js --wiring swapped         # the swapped-eyes check
node scripts/batch_run.js --innate 0 --runs 30     # any setting can be changed like this
```

**Rebuilding the brain file.** `web/brain_data.js` is already included. It only needs rebuilding if the
wall-dodge sub-circuit changes (`experiments/wall-dodge/scripts/build_subnetwork.py`, which needs the connectome
data, see [Getting the data](../README.md#getting-the-data)):

```bash
python scripts/export_brain.py
```

The connectome data is licensed CC-BY: credit Janelia FlyEM and the Male CNS connectome team if you reuse it.
