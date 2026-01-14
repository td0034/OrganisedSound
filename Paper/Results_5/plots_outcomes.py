from __future__ import annotations

from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import CONDITION_LABELS, CONDITION_ORDER


def _count_best_rank(end_df: pd.DataFrame) -> pd.Series:
    counts = {c: 0 for c in CONDITION_ORDER}
    if end_df.empty:
        return pd.Series(counts)
    for _, row in end_df.iterrows():
        winner = None
        for cond in CONDITION_ORDER:
            key = f"rank_{cond}"
            if key in end_df.columns and pd.notna(row.get(key)) and float(row.get(key)) == 1.0:
                winner = cond
                break
        if winner:
            counts[winner] += 1
    return pd.Series(counts)


def _count_categorical(end_df: pd.DataFrame, col: str) -> pd.Series:
    counts = {c: 0 for c in CONDITION_ORDER}
    if end_df.empty or col not in end_df.columns:
        return pd.Series(counts)
    for val in end_df[col].dropna().astype(str):
        if val in counts:
            counts[val] += 1
    return pd.Series(counts)


def plot_end_outcomes(end_df: pd.DataFrame, title: Optional[str] = None) -> plt.Figure:
    best_counts = _count_best_rank(end_df)
    inter_counts = _count_categorical(end_df, "most_intermedial")
    mismatch_counts = _count_categorical(end_df, "biggest_mismatch")

    questions = ["Best overall (rank=1)", "Most intermedial", "Biggest mismatch"]
    counts_by_question = [best_counts, inter_counts, mismatch_counts]

    fig, ax = plt.subplots(figsize=(8, 3))
    x = np.arange(len(questions))
    width = 0.22
    colors = {"A": "#bdd7e7", "B": "#6baed6", "C": "#2171b5"}

    for idx, cond in enumerate(CONDITION_ORDER):
        values = [counts.get(cond, 0) for counts in counts_by_question]
        ax.bar(x + (idx - 1) * width, values, width=width, color=colors[cond], label=cond)
        for xi, v in zip(x + (idx - 1) * width, values):
            ax.text(xi, v + 0.05, str(v), ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(questions, fontsize=9)
    ax.set_ylabel("Count")
    ax.legend(title="Condition", frameon=False)

    if title:
        ax.set_title(title, fontsize=11)
    fig.tight_layout()
    return fig
