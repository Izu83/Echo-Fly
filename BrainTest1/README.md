# BrainTest1: the fly brain experiments

Everything that uses the **male CNS connectome** (male fly brain + nerve cord, Janelia FlyEM,
CC-BY, [male-cns.janelia.org](https://male-cns.janelia.org/)).

| Folder / file | What it is |
|---|---|
| [`connectivity-check/`](connectivity-check/) | Is there wiring between candidate echo-sensing neurons and the turning / walking neurons? Charts, a 3D anatomical view and a write-up. |
| [`wall-dodge/`](wall-dodge/) | The first demo: a spiking circuit cut from the connectome steers a fly away from walls. Includes the interactive 3D replay. |
| [`explore.py`](explore.py) | Ten-line look at the annotation and connection tables. |
| [`download_data.py`](download_data.py) | Downloads the connectome tables into `data/` (not in git, they are ~23 GB). |
| `requirements.txt` | Python packages (`pip install -r requirements.txt`). |

## Getting the data

```bash
pip install -r requirements.txt
python download_data.py --core
```

`--core` (about 1.9 GB) is enough for `wall-dodge` and for everything in `connectivity-check` except
the 3D anatomical view. That view (`connectivity-check/scripts/build_3d.py`) also needs the synapse
location table, so for it run `python download_data.py` without `--core` (about 23 GB in total).
An interrupted download resumes when you run the command again.

The data is not stored in this repository (`data/` is git-ignored). It is licensed CC-BY: please credit
Janelia FlyEM and the Male CNS connectome team if you reuse it.

## Order to run things

1. `python download_data.py --core`
2. `connectivity-check/scripts/run_check.py`, then `extra_graphs.py` (optional, for the wiring analysis)
3. `wall-dodge/scripts/build_subnetwork.py`, `simulate.py`, `plot_results.py`, `build_web.py`

Each folder's own README has the details and the caveats for its results.
