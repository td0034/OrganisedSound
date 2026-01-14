from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


CONTRASTS = [("C", "A"), ("C", "B"), ("B", "A")]


def _bootstrap_ci(values: np.ndarray, n_boot: int = 2000, seed: int = 7) -> Tuple[float, float]:
    if values.size == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(n_boot, values.size), replace=True)
    means = samples.mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def plot_estimation(
    wide_df: pd.DataFrame,
    measures: List[Dict[str, str]],
) -> plt.Figure:
    nrows = len(measures)
    fig, axes = plt.subplots(nrows=nrows, ncols=1, figsize=(7, 2.5 * nrows), sharex=True)
    if nrows == 1:
        axes = [axes]

    for ax, measure in zip(axes, measures):
        column = measure["column"]
        label = measure["label"]
        pivot = wide_df.pivot(index="participant_id", columns="condition", values=column)
        for x_idx, (a, b) in enumerate(CONTRASTS):
            diffs = (pivot[a] - pivot[b]).dropna().to_numpy()
            if diffs.size == 0:
                continue
            jitter = (np.random.rand(diffs.size) - 0.5) * 0.2
            ax.scatter(np.full(diffs.size, x_idx) + jitter, diffs, color="#4c72b0", s=20)
            mean = float(np.mean(diffs))
            lo, hi = _bootstrap_ci(diffs)
            ax.errorbar(x_idx, mean, yerr=[[mean - lo], [hi - mean]], fmt="o", color="#000000", capsize=4)
        ax.axhline(0, color="#999999", linewidth=0.8)
        ax.set_ylabel(label, fontsize=9)
        ax.grid(axis="y", linestyle=":", linewidth=0.6, color="#cccccc")

    ax = axes[-1]
    ax.set_xticks(list(range(len(CONTRASTS))))
    ax.set_xticklabels([f"{a}-{b}" for a, b in CONTRASTS], fontsize=9)
    fig.tight_layout()
    return fig
