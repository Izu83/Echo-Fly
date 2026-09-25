"""
Download the Male CNS connectome flat files (Janelia FlyEM, CC-BY) into ./data/.

    python download_data.py --core    # ~1.9 GB: enough for connectivity-check and wall-dodge
    python download_data.py           # everything, ~23 GB (needed only for the 3D anatomical view)

Interrupted downloads resume where they stopped; finished files are skipped.
Source: https://male-cns.janelia.org/download/
"""

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome"
DATA = Path(__file__).resolve().parent / "data"

CORE = [
    "body-annotations-male-cns-v1.0-minconf-0.5.feather",
    "body-neurotransmitters-male-cns-v1.0.feather",
    "body-stats-male-cns-v1.0-minconf-0.5.feather",
    "connectome-weights-male-cns-v1.0-minconf-0.5.feather",
]
LARGE = [
    "syn-points-male-cns-v1.0-minconf-0.5.feather",
    "syn-partners-male-cns-v1.0-minconf-0.5.feather",
    "tbar-neurotransmitters-male-cns-v1.0.feather",
]
CHUNK = 1 << 20


def download(name: str) -> None:
    url, dest = f"{BASE}/{name}", DATA / name
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as r:
        total = int(r.headers["Content-Length"])
    have = dest.stat().st_size if dest.exists() else 0
    if have == total:
        print(f"skip  {name} (already complete)")
        return
    if have > total:
        have = 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    print(f"get   {name} ({total / 1e9:.2f} GB){f', resuming at {have / 1e9:.2f} GB' if have else ''}")
    with urllib.request.urlopen(req) as r, open(dest, "ab" if have else "wb") as f:
        done = have
        while chunk := r.read(CHUNK):
            f.write(chunk)
            done += len(chunk)
            print(f"\r      {done / total:6.1%}", end="", flush=True)
    print()
    if dest.stat().st_size != total:
        raise RuntimeError(f"{name}: size mismatch, run the script again to resume")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--core", action="store_true", help="only the ~1.9 GB of tables the simulation needs")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    for name in CORE if args.core else CORE + LARGE:
        try:
            download(name)
        except (urllib.error.URLError, RuntimeError, ConnectionError) as e:
            print(f"\nfailed: {e}\nrun the script again to resume.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
