"""
Quick look at the Male CNS connectome flat files (data/*.feather).
Source: https://male-cns.janelia.org/download/ (CC-BY, FlyEM / Janelia).

Run: python explore.py
"""

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent / "data"


def load(name: str) -> pd.DataFrame:
    return pd.read_feather(DATA / name)


def main():
    annotations = load("body-annotations-male-cns-v1.0-minconf-0.5.feather")
    weights = load("connectome-weights-male-cns-v1.0-minconf-0.5.feather")

    print(f"neurons (annotated bodies): {len(annotations):,}")
    print(f"annotation columns: {list(annotations.columns)}")
    print()
    print("neuron classes:")
    print(annotations["class"].value_counts().head(20) if "class" in annotations else "(no 'class' column found)")
    print()
    print(f"connections (edges): {len(weights):,}")
    print(f"weights columns: {list(weights.columns)}")


if __name__ == "__main__":
    main()
