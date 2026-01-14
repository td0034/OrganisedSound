from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import CONDITION_LABELS, CONDITION_ORDER


def plot_param_heatmap(param_counts: pd.DataFrame, title: Optional[str] = None) -> plt.Figure:
    if param_counts.empty:
        raise ValueError("No parameter influence data available.")
    pivot = param_counts.pivot_table(index="parameter", columns="condition", values="count", fill_value=0)
    pivot = pivot.reindex(columns=CONDITION_ORDER, fill_value=0)
    order = pivot.sum(axis=1).sort_values(ascending=False).index.tolist()
    pivot = pivot.loc[order]

    fig, ax = plt.subplots()
    im = ax.imshow(pivot.values, cmap="viridis")

    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(CONDITION_ORDER)))
    ax.set_xticklabels(CONDITION_ORDER, fontsize=8)
    ax.set_xlabel("Condition")
    ax.set_ylabel("")

    if title:
        ax.set_title(title, fontsize=11, loc="center", pad=16)

    condition_legend = (
        "Block Condition:\n"
        f"A - {CONDITION_LABELS['A']}\n"
        f"B - {CONDITION_LABELS['B']}\n"
        f"C - {CONDITION_LABELS['C']}"
    )
    fig.subplots_adjust(left=0.3, top=0.9)
    fig.text(
        0.02,
        0.98,
        condition_legend,
        ha="left",
        va="top",
        fontsize=8,
        bbox=dict(boxstyle="round", facecolor="white", edgecolor="#999999", linewidth=0.8),
    )
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, int(pivot.values[i, j]), ha="center", va="center", color="white", fontsize=7)

    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    return fig


def plot_param_bars(
    param_counts: pd.DataFrame,
    condition: str,
    title: Optional[str] = None,
    xmax: Optional[float] = None,
) -> plt.Figure:
    subset = param_counts[param_counts["condition"] == condition].copy()
    if subset.empty:
        raise ValueError(f"No parameter influence data for condition {condition}.")
    subset = subset.sort_values("count", ascending=True)

    fig, ax = plt.subplots()
    ax.barh(subset["parameter"], subset["count"], color="#4c72b0")
    ax.set_xlabel("Mentions")
    ax.set_ylabel("Parameter")
    ax.set_title(title or f"Parameter influence ({CONDITION_LABELS.get(condition, condition)})", fontsize=11)
    ax.grid(axis="x", linestyle=":", linewidth=0.6, color="#cccccc")
    if xmax is not None:
        ax.set_xlim(0, xmax)
    fig.tight_layout()
    return fig


def plot_param_stacked(param_counts: pd.DataFrame, title: Optional[str] = None) -> plt.Figure:
    if param_counts.empty:
        raise ValueError("No parameter influence data available.")
    pivot = param_counts.pivot_table(index="parameter", columns="condition", values="count", fill_value=0)
    pivot = pivot.reindex(columns=CONDITION_ORDER, fill_value=0)
    order = pivot.sum(axis=1).sort_values(ascending=False).index.tolist()
    pivot = pivot.loc[order]

    fig, ax = plt.subplots()
    colors = {"A": "#bdd7e7", "B": "#6baed6", "C": "#2171b5"}
    bottom = np.zeros(len(pivot.index))
    for cond in CONDITION_ORDER:
        values = pivot[cond].to_numpy()
        ax.bar(pivot.index, values, bottom=bottom, color=colors[cond], label=cond)
        bottom += values

    ax.set_ylabel("Mentions")
    ax.set_xlabel("")
    ax.legend(title="Condition", frameon=False)
    if title:
        ax.set_title(title, fontsize=11, pad=16)
    label_map = {
        "Neighbourhood (Local/Extended)": "Neighbourhood\n(Local/Extended)",
        "Min Population": "Min\nPopulation",
        "Max Population": "Max\nPopulation",
        "Min Neighbours": "Min\nNeighbours",
        "Max Neighbours": "Max\nNeighbours",
        "Loop On/Off": "Loop\nOn/Off",
        "Loop Length": "Loop\nLength",
        "Life Length": "Life\nLength",
    }
    labels = [label_map.get(name, name) for name in pivot.index.tolist()]
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, fontsize=8, rotation=70, ha="right", rotation_mode="anchor")
    for tick in ax.get_xticklabels():
        tick.set_multialignment("left")
    fig.tight_layout()
    return fig
