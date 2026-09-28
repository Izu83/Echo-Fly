# Experiments: the fly brain tests

Everything here uses the **male CNS connectome**: the male fly brain and nerve cord from Janelia FlyEM,
CC-BY, at [male-cns.janelia.org](https://male-cns.janelia.org/). The data lives in [`../data/`](../data/).

| Folder | What it is | Start with |
|---|---|---|
| [`connectivity-check/`](connectivity-check/) | Is there wiring between candidate echo-sensing neurons and the turning / walking neurons? Charts, a 3D anatomical view and a write-up. | its README |
| [`wall-dodge/`](wall-dodge/) | The first demo: a spiking circuit cut from the connectome steers a fly away from walls, with an interactive 3D replay. | `run.bat` |
| [`carry-walk-sim/`](carry-walk-sim/) | A 2D map you paint. The same circuit walks a fly from A to B, or fetches and carries a load, and learns the way with dopamine. | `run.bat` |

They build on each other: `wall-dodge` cuts the 820-neuron circuit out of the connectome, and `carry-walk-sim`
reuses that circuit (already exported, so it works without the data).

## Getting the data

From the Echo-Fly folder:

```bash
pip install -r requirements.txt
python data/download_data.py --core
```

- **`--core`** (about 1.9 GB) is enough for `wall-dodge` and for everything in `connectivity-check` except the 3D
  anatomical view.
- **Without `--core`** (about 24 GB in total) you also get the synapse location tables, which the 3D view
  (`connectivity-check/scripts/build_3d.py`) needs.
- An interrupted download resumes when you run the command again.

`python data/explore.py` prints a quick look at the tables. The data is not stored in git. It is licensed
CC-BY: please credit Janelia FlyEM and the Male CNS connectome team if you reuse it.

## Running things

- **wall-dodge:** double-click [`wall-dodge/run.bat`](wall-dodge/run.bat), or run it from a terminal. It
  installs the packages, downloads the data if it is missing, cuts the sub-circuit, runs the simulation and
  opens the 3D page. Finished steps are skipped, so a second run takes seconds. `run.bat force` redoes the
  simulation.
- **carry-walk-sim:** double-click [`carry-walk-sim/run.bat`](carry-walk-sim/run.bat), or open
  `carry-walk-sim/web/index.html` in a browser. It needs no install and no data.
- **connectivity-check:** `python connectivity-check/scripts/run_check.py`.

Each folder's own README has the details and the caveats for its results.
