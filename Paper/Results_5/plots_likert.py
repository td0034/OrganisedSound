from __future__ import annotations

from math import ceil
from typing import Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import CONDITION_LABELS, CONDITION_ORDER, ITEMS, LIKERT_SCALE


LIKERT_COLORS = {
    1: "#b2182b",
    2: "#d6604d",
    3: "#f4a582",
    4: "#e0e0e0",
    5: "#92c5de",
    6: "#4393c3",
    7: "#2166ac",
}


def _percent_counts(series: pd.Series) -> Dict[int, float]:
    counts = series.value_counts().to_dict()
    total = float(series.dropna().shape[0])
    return {val: (counts.get(val, 0) / total * 100.0 if total else 0.0) for val in LIKERT_SCALE}


def _draw_diverging(ax: plt.Axes, y: float, pct_map: Dict[int, float]) -> None:
    neg_vals = [pct_map[v] for v in [1, 2, 3]]
    pos_vals = [pct_map[v] for v in [5, 6, 7]]
    neutral = pct_map.get(4, 0.0)

    left = -sum(neg_vals) - neutral / 2.0
    x = left
    for val in [1, 2, 3]:
        width = pct_map.get(val, 0.0)
        if width:
            ax.barh(y, width, left=x, color=LIKERT_COLORS[val], edgecolor="white", height=0.6)
        x += width

    if neutral:
        ax.barh(y, neutral, left=-neutral / 2.0, color=LIKERT_COLORS[4], edgecolor="white", height=0.6)

    x = neutral / 2.0
    for val in [5, 6, 7]:
        width = pct_map.get(val, 0.0)
        if width:
            ax.barh(y, width, left=x, color=LIKERT_COLORS[val], edgecolor="white", height=0.6)
        x += width


def plot_likert_panel(
    long_df: pd.DataFrame,
    items: List[str],
    title: Optional[str] = None,
    ncols: int = 3,
) -> plt.Figure:
    nitems = len(items)
    ncols = min(ncols, nitems)
    nrows = int(ceil(nitems / ncols))

    # Target subplot size (inches) to keep A/B panels consistent.
    axes_w = 2.0
    axes_h = 0.9
    wspace_in = 0.4
    hspace_in = 0.45
    left_margin = 0.6
    right_margin = 0.2
    bottom_margin = 0.9
    top_margin = 1.2

    fig_w = left_margin + right_margin + axes_w * ncols + wspace_in * (ncols - 1)
    fig_h = bottom_margin + top_margin + axes_h * nrows + hspace_in * (nrows - 1)
    fig = plt.figure(figsize=(fig_w, fig_h))

    wspace = wspace_in / axes_w
    hspace = hspace_in / axes_h
    axes = fig.subplots(
        nrows=nrows,
        ncols=ncols,
        squeeze=False,
        gridspec_kw={"hspace": hspace, "wspace": wspace},
    )
    axes_list = axes.flatten()

    left = left_margin / fig_w
    right = 1 - (right_margin / fig_w)
    bottom = bottom_margin / fig_h
    top = 1 - (top_margin / fig_h)
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top)

    for ax in axes_list[nitems:]:
        ax.axis("off")

    for idx, item in enumerate(items):
        ax = axes_list[idx]
        subset = long_df[long_df["item"] == item]
        ys = np.arange(len(CONDITION_ORDER))
        for y_idx, cond in enumerate(CONDITION_ORDER):
            values = subset[subset["condition"] == cond]["value"].dropna()
            pct_map = _percent_counts(values) if not values.empty else {v: 0.0 for v in LIKERT_SCALE}
            _draw_diverging(ax, y_idx, pct_map)

        label = ITEMS[item]["label"]
        ax.set_title(label, fontsize=9)
        ax.set_yticks(ys)
        ax.set_yticklabels(CONDITION_ORDER, fontsize=8)
        ax.set_xlim(-100, 100)
        ax.axvline(0, color="#999999", linewidth=0.8)
        ax.set_xticks([-100, -50, 0, 50, 100])
        ax.set_xticklabels(["100", "50", "0", "50", "100"], fontsize=8)
        ax.grid(axis="x", linestyle=":", linewidth=0.6, color="#cccccc")

    if title:
        title_y = 1 - (top_margin / fig_h) * 0.2
        fig.text(0.5, title_y, title, ha="center", va="top", fontsize=11)

    handles = [plt.Rectangle((0, 0), 1, 1, color=LIKERT_COLORS[v]) for v in LIKERT_SCALE]
    labels = [str(v) for v in LIKERT_SCALE]
    fig.legend(
        handles,
        labels,
        title="Likert",
        loc="lower center",
        ncol=7,
        frameon=True,
        fontsize=8,
        facecolor="white",
        edgecolor="#999999",
    )
    condition_legend = (
        "Block Condition: "
        f"A - {CONDITION_LABELS['A']}   "
        f"B - {CONDITION_LABELS['B']}   "
        f"C - {CONDITION_LABELS['C']}"
    )
    legend_y = 1 - (top_margin / fig_h) * 0.6
    fig.text(
        0.5,
        legend_y,
        condition_legend,
        ha="center",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round", facecolor="white", edgecolor="#999999", linewidth=0.8),
    )
    return fig
