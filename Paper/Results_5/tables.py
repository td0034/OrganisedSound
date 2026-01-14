from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import CONDITION_LABELS, CONDITION_ORDER, CONSTRUCTS, ITEMS
from export import save_figure


TABLE2A_ITEMS = [
    "A_3",
    "A_1",
    "A_5",
    "A_6",
    "B_1",
    "B_3",
    "B_4",
    "B_5",
    "B_6",
    "B_10",
]


def _iqr(series: pd.Series) -> Optional[float]:
    if series.dropna().empty:
        return None
    return float(series.quantile(0.75) - series.quantile(0.25))


def _quartiles(series: pd.Series) -> Optional[tuple[float, float]]:
    if series.dropna().empty:
        return None
    return (float(series.quantile(0.25)), float(series.quantile(0.75)))


def _format_label(label: str) -> str:
    text = label.replace("_", " ").strip()
    if not text:
        return label
    return text[:1].upper() + text[1:]


def _apply_column_labels(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={c: _format_label(c) for c in df.columns})


def _save_table_figure(fig: plt.Figure, out_base: str, width: float, height: float) -> None:
    fig.set_size_inches(width, height)
    base = Path(out_base)
    base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(base.with_suffix(".eps")), bbox_inches="tight")
    fig.savefig(str(base.with_suffix(".pdf")), bbox_inches="tight")
    fig.savefig(str(base.with_suffix(".png")), dpi=300, bbox_inches="tight")
    fig.savefig(str(base.with_suffix(".tif")), dpi=600, bbox_inches="tight")


def _wrap_header(text: str) -> str:
    if text.strip().lower() == "participant id":
        return "ID"
    if " [" in text:
        return text.replace(" [", "\n[")
    if " " in text and len(text) > 12:
        return text.replace(" ", "\n")
    return text


def _render_table_figure(
    df: pd.DataFrame,
    out_base: str,
    col_widths: Optional[List[float]] = None,
    font_size: int = 10,
) -> None:
    fig, ax = plt.subplots()
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    headers = [_wrap_header(str(c)) for c in df.columns]
    rows = df.values.tolist()
    max_header_lines = max(h.count("\n") + 1 for h in headers)

    lengths = []
    for idx, col in enumerate(df.columns):
        values = [str(v) for v in df[col].tolist()]
        header_lines = headers[idx].split("\n")
        max_len = max([len(line) for line in header_lines] + [len(v) for v in values])
        lengths.append(max_len + 2)

    total = float(sum(lengths))
    widths = [length / total for length in lengths]
    if col_widths:
        widths = col_widths

    left = 0.02
    right = 0.98
    top = 0.95
    bottom = 0.05
    usable_width = right - left

    x_positions = []
    x_cursor = left
    for w in widths:
        x_positions.append(x_cursor)
        x_cursor += w * usable_width

    total_height = top - bottom
    row_height = total_height / (len(rows) + max_header_lines + 0.5)
    header_height = row_height * max_header_lines
    header_top = top - 0.01
    header_bottom = header_top - header_height - row_height * 0.1

    for idx, header in enumerate(headers):
        ax.text(
            x_positions[idx],
            header_top,
            header,
            ha="left",
            va="top",
            fontsize=font_size,
            fontfamily="Times New Roman",
            fontweight="bold",
        )

    y = header_bottom - row_height * 0.2
    for row in rows:
        for idx, value in enumerate(row):
            max_chars = max(8, int(widths[idx] * 140))
            wrapped = textwrap.fill(str(value), width=max_chars, break_long_words=False)
            ax.text(
                x_positions[idx],
                y,
                wrapped,
                ha="left",
                va="top",
                fontsize=font_size,
                fontfamily="Times New Roman",
            )
        y -= row_height

    ax.hlines(top, left, right, colors="#222222", linewidth=0.8)
    ax.hlines(header_bottom + row_height * 0.1, left, right, colors="#222222", linewidth=0.8)
    ax.hlines(y + row_height * 0.2, left, right, colors="#222222", linewidth=0.8)

    height = max(2.0, 0.28 * (len(rows) + max_header_lines + 1))
    _save_table_figure(fig, out_base, width=6.9, height=height)
    plt.close(fig)


def make_table1(participants_df: pd.DataFrame, outdir: str) -> str:
    if participants_df.empty:
        return ""
    columns = [
        "participant_id",
        "age_range",
        "musical_experience",
        "theory_familiarity",
        "generative_experience",
        "tonnetz_familiarity",
        "order",
    ]
    cols = [c for c in columns if c in participants_df.columns]
    table = participants_df[cols].copy()
    if "participant_id" in table.columns:
        ids = sorted(table["participant_id"].dropna().unique().tolist())
        pid_map = {pid: idx + 1 for idx, pid in enumerate(ids)}
        table["participant_id"] = table["participant_id"].map(pid_map)
    if "musical_experience" in table.columns:
        table["musical_experience"] = table["musical_experience"].astype(str).str.replace(r"\s*\(.*\)", "", regex=True)
    if "participant_id" in table.columns:
        table = table.sort_values("participant_id")
    table = _apply_column_labels(table)
    out_path = Path(outdir) / "Table1_participant_overview.csv"
    table.to_csv(out_path, index=False)
    widths = [
        0.07,  # Participant id
        0.14,  # Age range
        0.15,  # Musical experience
        0.14,  # Theory familiarity
        0.19,  # Generative experience
        0.15,  # Tonnetz familiarity
        0.16,  # Order
    ]
    _render_table_figure(table, str(Path(outdir) / "Table1_participant_overview"), col_widths=widths)
    return str(out_path)


def make_table2(long_df: pd.DataFrame, outdir: str) -> Dict[str, str]:
    if long_df.empty:
        return {}
    data = long_df[long_df["item"].isin(ITEMS.keys())].copy()
    data = data[data["value"].notna()]
    rows = []
    for item in sorted(ITEMS.keys()):
        for cond in CONDITION_ORDER:
            subset = data[(data["item"] == item) & (data["condition"] == cond)]
            if subset.empty:
                rows.append({
                    "item": item,
                    "item_label": ITEMS[item]["label"],
                    "condition": cond,
                    "condition_label": CONDITION_LABELS.get(cond, cond),
                    "n": 0,
                    "median": None,
                    "q1": None,
                    "q3": None,
                    "median_iqr": None,
                })
                continue
            q1q3 = _quartiles(subset["value"])
            q1 = q1q3[0] if q1q3 else None
            q3 = q1q3[1] if q1q3 else None
            median = float(subset["value"].median())
            median_iqr = f"{median:.2f} [{q1:.2f}, {q3:.2f}]" if q1 is not None and q3 is not None else None
            rows.append({
                "item": item,
                "item_label": ITEMS[item]["label"],
                "condition": cond,
                "condition_label": CONDITION_LABELS.get(cond, cond),
                "n": int(subset.shape[0]),
                "median": median,
                "q1": q1,
                "q3": q3,
                "median_iqr": median_iqr,
            })

    full = pd.DataFrame(rows)
    keep_cols = ["item", "item_label", "condition", "condition_label", "n", "median_iqr"]
    full = full[keep_cols].rename(columns={"median_iqr": "median [Q1, Q3]"})
    table2a = full[full["item"].isin(TABLE2A_ITEMS)].copy()

    outdir = Path(outdir)
    path_full = outdir / "Table2b_likert_full.csv"
    path_subset = outdir / "Table2a_likert_subset.csv"
    full_labeled = _apply_column_labels(full)
    table2a_labeled = _apply_column_labels(table2a)
    full_labeled.to_csv(path_full, index=False)
    table2a_labeled.to_csv(path_subset, index=False)
    _render_table_figure(table2a_labeled, str(outdir / "Table2a_likert_subset"), font_size=9)
    _render_table_figure(full_labeled, str(outdir / "Table2b_likert_full"), font_size=8)
    return {"Table2b": str(path_full), "Table2a": str(path_subset)}


def make_table3(outdir: str) -> str:
    rows = []
    for name, meta in CONSTRUCTS.items():
        construct = name.replace(" ", "\n")
        formula = meta.get("formula")
        if isinstance(formula, str) and len(formula) > 18:
            formula = formula.replace("(", "(\n")
        rows.append({
            "construct": construct,
            "items": ", ".join(meta.get("items", [])),
            "reversals": ", ".join(meta.get("reverse", [])),
            "formula": formula,
            "interpretation": meta.get("interpretation"),
        })
    df = pd.DataFrame(rows)
    out_path = Path(outdir) / "Table3_construct_mapping.csv"
    labeled = _apply_column_labels(df)
    labeled.to_csv(out_path, index=False)
    render_df = labeled.copy()
    if "Items" in render_df.columns:
        insert_at = list(render_df.columns).index("Items") + 1
        render_df.insert(insert_at, "", [""] * len(render_df))
    widths = [
        0.2,   # Construct
        0.24,  # Items
        0.04,  # Spacer
        0.22,  # Reversals
        0.15,  # Formula
        0.15,  # Interpretation
    ]
    _render_table_figure(
        render_df,
        str(Path(outdir) / "Table3_construct_mapping"),
        col_widths=widths,
        font_size=9,
    )
    return str(out_path)


def make_item_descriptives(long_df: pd.DataFrame, outdir: str) -> str:
    if long_df.empty:
        return ""
    data = long_df[long_df["item"].isin(ITEMS.keys())].copy()
    rows = []
    for item in sorted(ITEMS.keys()):
        for cond in CONDITION_ORDER:
            subset = data[(data["item"] == item) & (data["condition"] == cond)]
            if subset.empty:
                rows.append({
                    "item": item,
                    "condition": cond,
                    "n": 0,
                    "mean": None,
                    "sd": None,
                    "median": None,
                    "iqr": None,
                })
                continue
            vals = subset["value"].dropna()
            rows.append({
                "item": item,
                "condition": cond,
                "n": int(vals.shape[0]),
                "mean": float(vals.mean()),
                "sd": float(vals.std(ddof=1)) if vals.shape[0] > 1 else 0.0,
                "median": float(vals.median()),
                "iqr": _iqr(vals),
            })
    df = pd.DataFrame(rows)
    out_path = Path(outdir) / "Audit_item_descriptives.csv"
    df.to_csv(out_path, index=False)
    return str(out_path)


def make_param_counts_table(param_counts: pd.DataFrame, outdir: str) -> str:
    out_path = Path(outdir) / "Audit_param_influence_counts.csv"
    param_counts.to_csv(out_path, index=False)
    return str(out_path)
