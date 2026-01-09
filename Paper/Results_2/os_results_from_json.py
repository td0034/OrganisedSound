#!/usr/bin/env python3
"""
Organised Sound Results Generator
--------------------------------

Inputs:
  - sections_edited.json  (solo blocks + pre/post + end-of-session rankings)
  - participant_addendum_edited.json (addendum reflections)

Outputs:
  - ./figures/*.eps           (publication-ready EPS figures)
  - ./outputs/summary_numbers.json
  - ./outputs/tables/*.csv    (analysis tables you can paste into the paper)
  - ./outputs/log.txt         (parsing notes and warnings)

Design goals:
  - Be robust to slightly different JSON schemas (dict/list nesting, answers as dict or list).
  - Merge "pre" + "post" records per participant + condition (A/B/C).
  - Generate filenames that you can submit as separate EPS artefacts to Organised Sound.

Notes:
  - This script deliberately does NOT touch MIDI logs or audio feature extraction.
  - Statistical tests: Friedman (repeated measures), Wilcoxon pairwise with Holm correction.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

try:
    from scipy.stats import friedmanchisquare, wilcoxon, spearmanr
except Exception:
    friedmanchisquare = None
    wilcoxon = None
    spearmanr = None


# -----------------------------
# Configuration / conventions
# -----------------------------

CONDITION_LABELS = {
    "A": "Visual-only (no sound access during composition)",
    "B": "Audio-only (no visual access during composition)",
    "C": "Audiovisual (sound + visuals during composition)",
}

A_ITEMS = [f"A_{i}" for i in range(1, 8)]         # A_1..A_7
B_ITEMS = [f"B_{i}" for i in range(1, 13)]        # B_1..B_12

# Keys we search for to identify participant and section metadata
PID_KEYS = ["participant_id", "participantId", "participant_code", "participantCode", "pid", "code"]
SECTION_KEYS = ["section", "section_id", "sectionId", "section_key", "sectionKey", "page", "step", "form"]
TS_KEYS = ["created_at", "createdAt", "timestamp", "saved_at", "savedAt", "time"]

# End-of-session ranking keys you might have in your export (adjust if needed)
PREF_KEYS = [
    "overall_preference", "overallPreference", "rank1", "preference_rank1",
    "rank_A", "rank_B", "rank_C", "rankA", "rankB", "rankC",
    "most_intermedial", "mostIntermedial", "most_intermedial_choice",
]

# Parameter influence (your survey allowed selecting top influences)
PARAM_INFLUENCE_KEYS = ["param_influence", "paramInfluence", "most_influential_params", "influentialParams"]

# A/B/C detection patterns
COND_RE = re.compile(r"(?<![A-Z])([ABC])(?![A-Z])")
COND_WORD_HINTS = [
    ("visual-only", "A"), ("visual_only", "A"), ("visual", "A"),
    ("audio-only", "B"), ("audio_only", "B"), ("audio", "B"),
    ("audiovisual", "C"), ("audio-visual", "C"), ("av", "C"),
]


# -----------------------------
# Utilities
# -----------------------------

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def save_figure(fig: plt.Figure, outpath: str) -> None:
    """
    Save both EPS and PNG versions. If outpath ends with .eps, use it as the base.
    Otherwise, treat outpath as a base path without extension.
    """
    root, ext = os.path.splitext(outpath)
    base = root if ext.lower() == ".eps" else outpath
    fig.savefig(base + ".eps", format="eps", bbox_inches="tight")
    fig.savefig(base + ".png", format="png", dpi=300, bbox_inches="tight")

def _format_table_value(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and np.isnan(val):
        return ""
    if isinstance(val, (int, np.integer)):
        return str(int(val))
    if isinstance(val, (float, np.floating)):
        if abs(float(val)) < 0.0005:
            return "<0.001"
        return f"{float(val):.3f}"
    return str(val)

def save_table_figure(df: pd.DataFrame, columns: List[str], outpath: str,
                      title: Optional[str] = None, max_rows: int = 28,
                      fontsize: int = 8) -> None:
    """
    Render a table figure without vertical lines, and only three horizontal rules:
    top, header underline, bottom (per Organised Sound submission guidelines).
    """
    if df.empty:
        return

    data = [[_format_table_value(df.iloc[i][col]) for col in columns] for i in range(len(df))]

    def is_numeric_col(col_idx: int) -> bool:
        for row in data:
            val = row[col_idx]
            if val in ("", "NA"):
                continue
            try:
                float(val.replace("<", ""))
            except Exception:
                return False
        return True

    chunks = [data[i:i + max_rows] for i in range(0, len(data), max_rows)]
    base, ext = os.path.splitext(outpath)
    base = base if ext.lower() == ".eps" else outpath

    for idx, chunk in enumerate(chunks):
        suffix = f"_p{idx + 1}" if len(chunks) > 1 else ""
        page_out = base + suffix + ".eps"

        # Size heuristics: wider for more columns, taller for more rows.
        col_widths = []
        for c_idx, col in enumerate(columns):
            max_len = max([len(str(col))] + [len(str(r[c_idx])) for r in chunk])
            col_widths.append(max_len)
        fig_w = max(6.5, sum(col_widths) * 0.12)
        fig_h = max(2.5, (len(chunk) + 2) * 0.35)

        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.set_axis_off()
        if title:
            ax.set_title(title, fontsize=fontsize + 1, pad=10)

        table = ax.table(
            cellText=chunk,
            colLabels=columns,
            cellLoc="left",
            colLoc="left",
            loc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(fontsize)
        table.scale(1, 1.2)

        # Alignment: numeric columns right-aligned, text left-aligned.
        for c_idx in range(len(columns)):
            align = "right" if is_numeric_col(c_idx) else "left"
            for r_idx in range(len(chunk) + 1):
                cell = table[(r_idx, c_idx)]
                cell.set_text_props(ha=align)

        # Remove all cell edges (no vertical lines).
        for cell in table.get_celld().values():
            cell.set_linewidth(0.0)
            cell.set_edgecolor("white")

        # Draw only top, header, and bottom horizontal rules.
        fig.canvas.draw()
        cells = table.get_celld()
        header_cells = [cells[(0, c)] for c in range(len(columns))]
        x0 = min(c.get_x() for c in header_cells)
        x1 = max(c.get_x() + c.get_width() for c in header_cells)
        y_top = max(c.get_y() + c.get_height() for c in header_cells)
        y_header_bottom = min(c.get_y() for c in header_cells)
        last_row_idx = len(chunk)
        last_cells = [cells[(last_row_idx, c)] for c in range(len(columns))]
        y_bottom = min(c.get_y() for c in last_cells)
        ax.hlines([y_top, y_header_bottom, y_bottom], x0, x1, colors="black",
                  linewidths=0.8, transform=ax.transAxes)

        fig.tight_layout()
        save_figure(fig, page_out)
        plt.close(fig)

def safe_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, float):
        if np.isnan(x):
            return None
        return int(x)
    if isinstance(x, str):
        s = x.strip()
        if s == "":
            return None
        # accept "7", "7.0"
        try:
            return int(float(s))
        except Exception:
            return None
    return None

def parse_timestamp(obj: Dict[str, Any]) -> Optional[datetime]:
    for k in TS_KEYS:
        if k in obj:
            v = obj.get(k)
            if isinstance(v, (int, float)):
                # epoch seconds
                try:
                    return datetime.fromtimestamp(float(v))
                except Exception:
                    return None
            if isinstance(v, str):
                # try ISO
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ",
                            "%Y-%m-%dT%H:%M:%S%z",
                            "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(v, fmt)
                    except Exception:
                        pass
    return None

def find_first(obj: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for k in keys:
        if k in obj:
            return obj.get(k)
    return None

def guess_condition_from_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    for hint, cond in COND_WORD_HINTS:
        if hint in t:
            return cond
    m = COND_RE.search(text.upper())
    if m:
        c = m.group(1)
        if c in ("A", "B", "C"):
            return c
    return None


def iter_dicts(obj: Any) -> Iterable[Dict[str, Any]]:
    """Yield dicts from any nested JSON structure."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_dicts(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from iter_dicts(it)


def extract_answers_block(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract answers from a record. Supports:
      - answers: { "A_1": 7, ... }
      - answers: [ { "id": "A_1", "value": 7 }, ... ]
      - responses / data / fields with similar schemas
    """
    candidates = []
    for key in ["answers", "responses", "response", "data", "fields", "values", "payload"]:
        if key in record:
            candidates.append(record[key])

    out: Dict[str, Any] = {}

    def ingest(obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, dict):
            # if this dict looks like {id:..., value:...}
            if ("id" in obj or "qid" in obj or "name" in obj) and ("value" in obj or "answer" in obj or "response" in obj):
                qid = obj.get("id") or obj.get("qid") or obj.get("name")
                val = obj.get("value") if "value" in obj else obj.get("answer") if "answer" in obj else obj.get("response")
                if isinstance(qid, str):
                    out[qid.strip()] = val
            else:
                # otherwise treat keys as question ids
                for k, v in obj.items():
                    if isinstance(k, str) and (k.startswith("A_") or k.startswith("B_") or k in PREF_KEYS or k in PARAM_INFLUENCE_KEYS):
                        out[k.strip()] = v
        elif isinstance(obj, list):
            for it in obj:
                ingest(it)

    for c in candidates:
        ingest(c)

    # Also: sometimes answers are top-level keys directly in the record.
    for k, v in record.items():
        if isinstance(k, str) and (k.startswith("A_") or k.startswith("B_") or k in PREF_KEYS or k in PARAM_INFLUENCE_KEYS):
            out.setdefault(k.strip(), v)

    return out


def classify_record(record: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Return (participant_id, condition, phase) where phase in {"pre","post","end","unknown"}.
    We infer condition/phase from explicit fields or section identifiers.
    """
    pid = find_first(record, PID_KEYS)
    if isinstance(pid, (int, float)):
        pid = str(pid)
    pid = (pid.strip() if isinstance(pid, str) else None)

    section = find_first(record, SECTION_KEYS)
    section_str = str(section) if section is not None else ""
    section_lower = section_str.lower()

    # Condition
    cond = None
    # explicit
    for k in ["condition", "block", "trial", "cond"]:
        if k in record and isinstance(record[k], str):
            if record[k].strip().upper() in ("A", "B", "C"):
                cond = record[k].strip().upper()
    if cond is None:
        cond = guess_condition_from_text(section_str)

    # Phase
    phase = "unknown"
    if any(x in section_lower for x in ["pre", "parta", "part_a", "before", "compose", "during"]):
        phase = "pre"
    if any(x in section_lower for x in ["post", "partb", "part_b", "reveal", "after", "replay"]):
        phase = "post"
    if any(x in section_lower for x in ["end", "final", "ranking", "rank", "overall"]):
        phase = "end"

    # If answers contain mostly A_ keys or B_ keys, override
    ans = extract_answers_block(record)
    a_hits = sum(1 for k in ans.keys() if k.startswith("A_"))
    b_hits = sum(1 for k in ans.keys() if k.startswith("B_"))
    if a_hits >= 3 and b_hits == 0:
        phase = "pre"
    if b_hits >= 3 and a_hits == 0:
        phase = "post"

    return pid, cond, phase


def holm_correction(pvals: List[float]) -> List[float]:
    """Holm–Bonferroni correction."""
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.zeros(m, dtype=float)
    for i, idx in enumerate(order):
        adj[idx] = min((m - i) * pvals[idx], 1.0)
    # ensure monotonicity
    for i in range(m - 2, -1, -1):
        idx_i = order[i]
        idx_j = order[i + 1]
        adj[idx_i] = min(adj[idx_i], adj[idx_j])
    return adj.tolist()


def kendalls_w_from_friedman(chi2: float, n: int, k: int) -> Optional[float]:
    # W = chi2 / (n*(k-1))
    if n <= 0 or k <= 1:
        return None
    return float(chi2) / float(n * (k - 1))


# -----------------------------
# Core pipeline
# -----------------------------

def load_records(sections_json: Any, log_lines: List[str]) -> pd.DataFrame:
    """
    Extract likely records from an arbitrary JSON structure.
    We treat each dict that contains a participant id or an answers block as a candidate record.
    """
    recs = []
    for d in iter_dicts(sections_json):
        pid, cond, phase = classify_record(d)
        answers = extract_answers_block(d)
        # Only keep if it looks relevant
        if pid or any(k.startswith(("A_", "B_")) for k in answers.keys()) or any(k in answers for k in PREF_KEYS):
            ts = parse_timestamp(d)
            recs.append({
                "participant_id": pid,
                "condition": cond,
                "phase": phase,
                "timestamp": ts.isoformat() if ts else None,
                "section_raw": str(find_first(d, SECTION_KEYS) or ""),
                **answers,
            })

    df = pd.DataFrame(recs)
    log_lines.append(f"Candidate records extracted: {len(df)}")
    return df


def merge_pre_post(df_records: pd.DataFrame, log_lines: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Merge pre + post per participant + condition.
    Returns:
      df_blocks: one row per participant+condition with A_*, B_*, plus metadata.
      df_end: end-of-session records (rankings etc) per participant.
    """
    df = df_records.copy()

    # Ensure condition uppercase A/B/C where possible
    df["condition"] = df["condition"].astype(str).str.strip().str.upper()
    df.loc[~df["condition"].isin(["A", "B", "C"]), "condition"] = None

    # Drop rows with no participant id (cannot merge)
    df = df[~df["participant_id"].isna() & (df["participant_id"].astype(str).str.strip() != "")]
    df["participant_id"] = df["participant_id"].astype(str).str.strip()

    # Split phases
    df_pre = df[df["phase"] == "pre"].copy()
    df_post = df[df["phase"] == "post"].copy()
    df_end = df[df["phase"] == "end"].copy()

    # Keep only A_ items in pre, B_ in post, but allow extra text fields to flow through
    pre_keep = ["participant_id", "condition", "timestamp", "section_raw"] + A_ITEMS + ["aim", "strategy", "param_influence"]
    post_keep = ["participant_id", "condition", "timestamp", "section_raw"] + B_ITEMS + ["expectation_vs_outcome", "interference_notes", "param_influence"]

    for col in pre_keep:
        if col not in df_pre.columns:
            df_pre[col] = None
    for col in post_keep:
        if col not in df_post.columns:
            df_post[col] = None

    df_pre = df_pre[pre_keep]
    df_post = df_post[post_keep]

    # If multiple saves exist per participant+condition+phase, keep the latest by timestamp order or row order
    df_pre["_ord"] = np.arange(len(df_pre))
    df_post["_ord"] = np.arange(len(df_post))

    def pick_last(g: pd.DataFrame) -> pd.Series:
        if "timestamp" in g.columns and g["timestamp"].notna().any():
            # sort by timestamp if parseable; else by _ord
            try:
                tt = pd.to_datetime(g["timestamp"], errors="coerce")
                g2 = g.assign(_t=tt).sort_values(["_t", "_ord"])
                return g2.iloc[-1]
            except Exception:
                pass
        return g.sort_values("_ord").iloc[-1]

    df_pre_last = df_pre.groupby(["participant_id", "condition"], dropna=False).apply(pick_last).reset_index(drop=True)
    df_post_last = df_post.groupby(["participant_id", "condition"], dropna=False).apply(pick_last).reset_index(drop=True)

    # Merge
    df_blocks = pd.merge(df_pre_last, df_post_last, on=["participant_id", "condition"], how="outer", suffixes=("_pre", "_post"))

    # Derive within-participant condition order from timestamps if possible
    df_blocks["_t_pre"] = pd.to_datetime(df_blocks["timestamp_pre"], errors="coerce")
    df_blocks["_t_post"] = pd.to_datetime(df_blocks["timestamp_post"], errors="coerce")
    df_blocks["_t_any"] = df_blocks["_t_pre"].fillna(df_blocks["_t_post"])
    df_blocks["block_position"] = df_blocks.groupby("participant_id")["_t_any"].rank(method="first").astype("Int64")

    log_lines.append(f"Merged block rows (participant x condition): {len(df_blocks)}")

    return df_blocks, df_end


def coerce_likert(df_blocks: pd.DataFrame) -> pd.DataFrame:
    df = df_blocks.copy()
    for col in A_ITEMS + B_ITEMS:
        if col in df.columns:
            df[col] = df[col].apply(safe_int)
    return df


# -----------------------------
# Stats + plotting helpers
# -----------------------------

def friedman_item(df: pd.DataFrame, item: str) -> Dict[str, Any]:
    out = {"item": item, "test": "friedman", "n": 0, "chi2": None, "p": None, "kendalls_w": None}
    if friedmanchisquare is None:
        out["note"] = "scipy not available"
        return out
    wide = df.pivot_table(index="participant_id", columns="condition", values=item, aggfunc="first")
    wide = wide[["A", "B", "C"]] if set(["A", "B", "C"]).issubset(wide.columns) else wide
    wide = wide.dropna()
    if wide.shape[0] < 3:
        out["note"] = "insufficient complete cases"
        return out
    stat = friedmanchisquare(wide["A"], wide["B"], wide["C"])
    out["n"] = int(wide.shape[0])
    out["chi2"] = float(stat.statistic)
    out["p"] = float(stat.pvalue)
    out["kendalls_w"] = kendalls_w_from_friedman(out["chi2"], out["n"], 3)
    return out


def wilcoxon_pairs(df: pd.DataFrame, item: str) -> pd.DataFrame:
    if wilcoxon is None:
        return pd.DataFrame([{"item": item, "note": "scipy not available"}])

    wide = df.pivot_table(index="participant_id", columns="condition", values=item, aggfunc="first")
    needed = ["A", "B", "C"]
    if not set(needed).issubset(wide.columns):
        return pd.DataFrame([{"item": item, "note": "missing conditions in data"}])

    pairs = [("A", "B"), ("A", "C"), ("B", "C")]
    rows = []
    pvals = []

    # compute raw p
    for x, y in pairs:
        w = wide[[x, y]].dropna()
        if w.shape[0] < 3:
            rows.append({"item": item, "pair": f"{x}-{y}", "n": int(w.shape[0]), "stat": None, "p": None})
            pvals.append(np.nan)
            continue
        res = wilcoxon(w[x], w[y], zero_method="wilcox", correction=False, alternative="two-sided", mode="auto")
        rows.append({"item": item, "pair": f"{x}-{y}", "n": int(w.shape[0]), "stat": float(res.statistic), "p": float(res.pvalue)})
        pvals.append(float(res.pvalue))

    # Holm correction (ignore NaNs)
    valid_idx = [i for i, p in enumerate(pvals) if p == p]
    adj = [np.nan] * len(pvals)
    if valid_idx:
        adj_vals = holm_correction([pvals[i] for i in valid_idx])
        for j, i in enumerate(valid_idx):
            adj[i] = adj_vals[j]

    for i, a in enumerate(adj):
        rows[i]["p_holm"] = (float(a) if a == a else None)

    return pd.DataFrame(rows)


def describe_by_condition(df: pd.DataFrame, item: str) -> pd.DataFrame:
    rows = []
    for c in ["A", "B", "C"]:
        s = df.loc[df["condition"] == c, item].dropna()
        if len(s) == 0:
            rows.append({"item": item, "condition": c, "n": 0, "mean": None, "sd": None, "median": None, "iqr": None})
            continue
        rows.append({
            "item": item,
            "condition": c,
            "n": int(len(s)),
            "mean": float(np.mean(s)),
            "sd": float(np.std(s, ddof=1)) if len(s) > 1 else 0.0,
            "median": float(np.median(s)),
            "iqr": float(np.percentile(s, 75) - np.percentile(s, 25)),
        })
    return pd.DataFrame(rows)


def save_boxplot_eps(df: pd.DataFrame, items: List[str], title: str, ylabel: str, outpath: str) -> None:
    # Long form
    rows = []
    for item in items:
        for c in ["A", "B", "C"]:
            vals = df.loc[df["condition"] == c, item].dropna().tolist()
            for v in vals:
                rows.append({"condition": c, "item": item, "value": v})
    long = pd.DataFrame(rows)
    if long.empty:
        return

    # Grouped boxplots by condition, with item offsets
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    conds = ["A", "B", "C"]
    x_base = np.arange(len(conds))
    width = 0.22 if len(items) > 1 else 0.40
    offsets = np.linspace(-width, width, num=len(items)) if len(items) > 1 else [0.0]

    for i, item in enumerate(items):
        data = [long[(long["condition"] == c) & (long["item"] == item)]["value"].values for c in conds]
        pos = x_base + offsets[i]
        ax.boxplot(data, positions=pos, widths=width, patch_artist=False, showfliers=False)

    ax.set_xticks(x_base)
    ax.set_xticklabels([f"{c}\n{CONDITION_LABELS[c].split('(')[0].strip()}" for c in conds], fontsize=8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_ylim(1, 7)
    ax.grid(axis="y", linestyle=":", linewidth=0.6)

    # Legend-like annotation (simple, monochrome)
    if len(items) > 1:
        legend_text = " / ".join(items)
        ax.text(0.5, -0.22, legend_text, transform=ax.transAxes, ha="center", va="top", fontsize=8)

    fig.tight_layout()
    save_figure(fig, outpath)
    plt.close(fig)

def save_boxplot_grouped(df: pd.DataFrame, value_col: str, group_col: str,
                         title: str, ylabel: str, outpath: str) -> None:
    groups = sorted(df[group_col].dropna().unique().tolist())
    if not groups:
        return
    data = [df.loc[df[group_col] == g, value_col].dropna().values for g in groups]
    if not any(len(d) for d in data):
        return

    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.boxplot(data, widths=0.5, patch_artist=False, showfliers=False)
    ax.set_xticks(range(1, len(groups) + 1))
    ax.set_xticklabels([str(g) for g in groups])
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle=":", linewidth=0.6)
    fig.tight_layout()
    save_figure(fig, outpath)
    plt.close(fig)


def save_bar_counts_eps(counts: pd.DataFrame, title: str, ylabel: str, outpath: str) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    x = np.arange(len(counts))
    ax.bar(x, counts["count"].values)
    ax.set_xticks(x)
    ax.set_xticklabels(counts["label"].values, rotation=0, fontsize=9)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle=":", linewidth=0.6)
    fig.tight_layout()
    save_figure(fig, outpath)
    plt.close(fig)


def normalise_param_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, float) and np.isnan(x):
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    if isinstance(x, str):
        # try JSON list
        s = x.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                arr = json.loads(s)
                if isinstance(arr, list):
                    return [str(i).strip() for i in arr if str(i).strip()]
            except Exception:
                pass
        # comma separated
        if "," in s:
            return [p.strip() for p in s.split(",") if p.strip()]
        return [s]
    return [str(x).strip()]


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", required=True, help="Path to sections_edited.json")
    ap.add_argument("--addendum", required=False, help="Path to participant_addendum_edited.json")
    ap.add_argument("--out", default="outputs", help="Output directory for tables/summaries")
    ap.add_argument("--fig", default=os.path.join("outputs", "figures"),
                    help="Root output directory for EPS+PNG figures (core/ additional)")
    args = ap.parse_args()

    ensure_dir(args.out)
    ensure_dir(args.fig)
    ensure_dir(os.path.join(args.out, "tables"))
    core_fig_dir = os.path.join(args.fig, "core")
    add_fig_dir = os.path.join(args.fig, "additional")
    ensure_dir(core_fig_dir)
    ensure_dir(add_fig_dir)

    log_lines: List[str] = []

    with open(args.sections, "r", encoding="utf-8") as f:
        sections_json = json.load(f)

    df_records = load_records(sections_json, log_lines)
    df_blocks, df_end = merge_pre_post(df_records, log_lines)
    df_blocks = coerce_likert(df_blocks)

    # Quick sanity check for the console + log
    n_participants = int(df_blocks["participant_id"].nunique()) if not df_blocks.empty else 0
    n_blocks = int(df_blocks[df_blocks["condition"].isin(["A", "B", "C"])].shape[0]) if not df_blocks.empty else 0
    log_lines.append(f"Sanity: participants={n_participants}, blocks={n_blocks}")
    print(f"Sanity check: participants={n_participants}, blocks={n_blocks}")

    # Basic counts
    participants = sorted(df_blocks["participant_id"].dropna().unique().tolist())
    N_participants = len(participants)
    N_blocks_total = int(df_blocks[df_blocks["condition"].isin(["A", "B", "C"])].shape[0])
    N_blocks_expected = N_participants * 3

    # Missingness across Likert
    likert_cols = [c for c in A_ITEMS + B_ITEMS if c in df_blocks.columns]
    miss = df_blocks[likert_cols].isna().mean().mean() if likert_cols else np.nan

    summary_numbers = {
        "N_participants": N_participants,
        "N_blocks_total": N_blocks_total,
        "N_blocks_expected": N_blocks_expected,
        "missing_pct": None if miss != miss else float(miss * 100.0),
    }

    # -------------------------
    # Rankings (if available)
    # -------------------------
    # Attempt to extract rank-1 preference and "most intermedial"
    pref_rank1 = []
    most_intermedial = []

    if not df_end.empty:
        # Consolidate per participant (latest end record)
        df_end["_ord"] = np.arange(len(df_end))
        df_end_last = df_end.groupby("participant_id").tail(1).copy()

        for _, r in df_end_last.iterrows():
            # try common key variants
            # If stored as literal "A"/"B"/"C" in a key:
            val_pref = None
            for k in ["rank1", "overall_preference", "overallPreference", "preference_rank1"]:
                if k in r and isinstance(r[k], str) and r[k].strip().upper() in ("A", "B", "C"):
                    val_pref = r[k].strip().upper()
            # If stored as numeric rank_A/rank_B/rank_C:
            if val_pref is None:
                ranks = {}
                for cond in ["A", "B", "C"]:
                    for key in [f"rank_{cond}", f"rank{cond}"]:
                        if key in r and r[key] is not None:
                            try:
                                ranks[cond] = int(str(r[key]).strip())
                            except Exception:
                                pass
                for cond, rank in ranks.items():
                    if rank == 1:
                        val_pref = cond
            if val_pref:
                pref_rank1.append(val_pref)

            val_int = None
            for k in ["most_intermedial", "mostIntermedial", "most_intermedial_choice"]:
                if k in r and isinstance(r[k], str) and r[k].strip().upper() in ("A", "B", "C"):
                    val_int = r[k].strip().upper()
            if val_int:
                most_intermedial.append(val_int)

    def counts_abc(arr: List[str]) -> Dict[str, int]:
        return {c: int(sum(1 for x in arr if x == c)) for c in ["A", "B", "C"]}

    pref_counts = counts_abc(pref_rank1)
    inter_counts = counts_abc(most_intermedial)

    summary_numbers.update({
        "pref_A_n": pref_counts["A"],
        "pref_B_n": pref_counts["B"],
        "pref_C_n": pref_counts["C"],
        "most_intermedial_A_n": inter_counts["A"],
        "most_intermedial_B_n": inter_counts["B"],
        "most_intermedial_C_n": inter_counts["C"],
    })

    # -------------------------
    # Descriptives + tests
    # -------------------------
    stats_rows = []
    pairwise_rows = []

    for item in [*A_ITEMS, *B_ITEMS]:
        if item not in df_blocks.columns:
            continue
        stats_rows.append(friedman_item(df_blocks[df_blocks["condition"].isin(["A", "B", "C"])], item))
        pw = wilcoxon_pairs(df_blocks[df_blocks["condition"].isin(["A", "B", "C"])], item)
        pairwise_rows.append(pw)

    df_stats = pd.DataFrame(stats_rows)
    df_pairwise = pd.concat(pairwise_rows, ignore_index=True) if pairwise_rows else pd.DataFrame()

    df_desc = pd.concat([describe_by_condition(df_blocks[df_blocks["condition"].isin(["A", "B", "C"])], it)
                         for it in [*A_ITEMS, *B_ITEMS] if it in df_blocks.columns],
                        ignore_index=True) if likert_cols else pd.DataFrame()

    # Spearman A_2 vs A_3 (pooled across conditions; optional)
    if spearmanr is not None and "A_2" in df_blocks.columns and "A_3" in df_blocks.columns:
        tmp = df_blocks[df_blocks["condition"].isin(["A", "B", "C"])][["A_2", "A_3"]].dropna()
        if len(tmp) >= 5:
            rho, p = spearmanr(tmp["A_2"], tmp["A_3"])
            summary_numbers["A2A3_rho"] = float(rho)
            summary_numbers["A2A3_p"] = float(p)

    # Save tables
    df_blocks.to_csv(os.path.join(args.out, "tables", "blocks_merged.csv"), index=False)
    df_desc.to_csv(os.path.join(args.out, "tables", "likert_descriptives.csv"), index=False)
    df_stats.to_csv(os.path.join(args.out, "tables", "friedman_tests.csv"), index=False)
    df_pairwise.to_csv(os.path.join(args.out, "tables", "wilcoxon_pairwise.csv"), index=False)

    # Save summary numbers
    with open(os.path.join(args.out, "summary_numbers.json"), "w", encoding="utf-8") as f:
        json.dump(summary_numbers, f, indent=2)

    # -------------------------
    # Figures (EPS)
    # -------------------------

    # Fig 1: preference / most intermedial
    if sum(pref_counts.values()) > 0:
        counts = pd.DataFrame({
            "label": ["A", "B", "C"],
            "count": [pref_counts["A"], pref_counts["B"], pref_counts["C"]],
        })
        save_bar_counts_eps(
            counts,
            "Rank-1 preference by condition",
            "Count",
            os.path.join(core_fig_dir, "Fig01_preference_rank1.eps"),
        )

    if sum(inter_counts.values()) > 0:
        counts = pd.DataFrame({
            "label": ["A", "B", "C"],
            "count": [inter_counts["A"], inter_counts["B"], inter_counts["C"]],
        })
        save_bar_counts_eps(
            counts,
            "“Most intermedial” choice by condition",
            "Count",
            os.path.join(core_fig_dir, "Fig01b_most_intermedial_choice.eps"),
        )

    # Fig 2-3: key pre-reveal
    if "A_3" in df_blocks.columns:
        save_boxplot_eps(df_blocks, ["A_3"], "A_3: Able to steer toward intention", "Likert (1–7)",
                         os.path.join(core_fig_dir, "Fig02_A3_steerability.eps"))
    if "A_6" in df_blocks.columns:
        save_boxplot_eps(df_blocks, ["A_6"], "A_6: Unpredictable / frustrating", "Likert (1–7)",
                         os.path.join(core_fig_dir, "Fig03_A6_frustration.eps"))

    # Fig 4: post-reveal core (fusion/equality/coherence)
    for k in ["B_1", "B_2", "B_3"]:
        if k not in df_blocks.columns:
            break
    else:
        save_boxplot_eps(df_blocks, ["B_1", "B_2", "B_3"],
                         "Post-reveal: Fusion, equality, coherence (B_1–B_3)",
                         "Likert (1–7)",
                         os.path.join(core_fig_dir, "Fig04_B1_B2_B3_core_intermediality.eps"))

    # Fig 5: interference + overload
    for k in ["B_4", "B_5", "B_6"]:
        if k not in df_blocks.columns:
            break
    else:
        save_boxplot_eps(df_blocks, ["B_4", "B_5", "B_6"],
                         "Post-reveal: Interference and overload (B_4–B_6)",
                         "Likert (1–7)",
                         os.path.join(core_fig_dir, "Fig05_B4_B5_B6_interference_overload.eps"))

    # Fig 6: reliance (visual vs theory)
    for k in ["B_11", "B_12"]:
        if k not in df_blocks.columns:
            break
    else:
        save_boxplot_eps(df_blocks, ["B_11", "B_12"],
                         "Post-reveal: Reliance on visual cues vs theory cues (B_11–B_12)",
                         "Likert (1–7)",
                         os.path.join(core_fig_dir, "Fig06_B11_B12_cue_reliance.eps"))

    # Fig 7: parameter influence frequencies
    df_param_counts: Optional[pd.DataFrame] = None
    if "param_influence_pre" in df_blocks.columns or "param_influence_post" in df_blocks.columns or "param_influence" in df_blocks.columns:
        # combine any available
        param_cols = [c for c in ["param_influence_pre", "param_influence_post", "param_influence"] if c in df_blocks.columns]
        rows = []
        for _, r in df_blocks.iterrows():
            cond = r.get("condition")
            if cond not in ("A", "B", "C"):
                continue
            plist = []
            for pc in param_cols:
                plist += normalise_param_list(r.get(pc))
            # de-dup within block
            plist = [p for p in dict.fromkeys(plist) if p]
            for p in plist:
                rows.append({"condition": cond, "param": p})

        dfp = pd.DataFrame(rows)
        if not dfp.empty:
            # counts
            tab = dfp.groupby(["condition", "param"]).size().reset_index(name="count")
            tab.to_csv(os.path.join(args.out, "tables", "param_influence_counts.csv"), index=False)
            df_param_counts = tab.copy()

            # choose top params overall for plotting
            overall = dfp["param"].value_counts().head(10).index.tolist()
            # Build wide counts (A/B/C x param)
            wide = tab.pivot_table(index="param", columns="condition", values="count", aggfunc="sum").fillna(0)
            wide = wide.loc[[p for p in overall if p in wide.index]]

            fig, ax = plt.subplots(figsize=(7.2, 4.0))
            x = np.arange(len(wide.index))
            width = 0.25
            ax.bar(x - width, wide.get("A", pd.Series([0]*len(x), index=wide.index)).values, width, label="A")
            ax.bar(x,         wide.get("B", pd.Series([0]*len(x), index=wide.index)).values, width, label="B")
            ax.bar(x + width, wide.get("C", pd.Series([0]*len(x), index=wide.index)).values, width, label="C")
            ax.set_xticks(x)
            ax.set_xticklabels(wide.index.tolist(), rotation=45, ha="right", fontsize=8)
            ax.set_ylabel("Selections (count)")
            ax.set_title("Most influential parameters (top 10 overall)")
            ax.grid(axis="y", linestyle=":", linewidth=0.6)
            ax.legend(frameon=False)
            fig.tight_layout()
            save_figure(fig, os.path.join(core_fig_dir, "Fig07_param_influence_top10.eps"))
            plt.close(fig)

    # -------------------------
    # Additional analyses + tables
    # -------------------------
    df_blocks_valid = df_blocks[df_blocks["condition"].isin(["A", "B", "C"])].copy()

    # Composite indices (optional)
    composite_items = []
    if all(c in df_blocks_valid.columns for c in ["B_1", "B_2", "B_3", "B_4", "B_5", "B_6"]):
        df_blocks_valid["intermediality_index"] = (
            df_blocks_valid[["B_1", "B_2", "B_3", "B_4"]].mean(axis=1)
            - df_blocks_valid[["B_5", "B_6"]].mean(axis=1)
        )
        composite_items.append("intermediality_index")
        save_boxplot_grouped(
            df_blocks_valid,
            "intermediality_index",
            "condition",
            "Intermediality index (B_1–B_4 minus B_5–B_6)",
            "Index",
            os.path.join(add_fig_dir, "Fig08_intermediality_index.eps"),
        )

    if all(c in df_blocks_valid.columns for c in ["A_2", "A_3", "A_4", "A_6"]):
        df_blocks_valid["agency_index"] = (
            df_blocks_valid[["A_2", "A_3", "A_4"]].mean(axis=1)
            - df_blocks_valid[["A_6"]].mean(axis=1)
        )
        composite_items.append("agency_index")
        save_boxplot_grouped(
            df_blocks_valid,
            "agency_index",
            "condition",
            "Agency index (A_2–A_4 minus A_6)",
            "Index",
            os.path.join(add_fig_dir, "Fig09_agency_index.eps"),
        )

    if composite_items:
        df_blocks_valid[["participant_id", "condition", *composite_items]].to_csv(
            os.path.join(args.out, "tables", "composite_indices.csv"), index=False
        )
        comp_desc = pd.concat(
            [describe_by_condition(df_blocks_valid, it) for it in composite_items],
            ignore_index=True,
        )
        comp_stats = pd.DataFrame(
            [friedman_item(df_blocks_valid, it) for it in composite_items]
        )
        comp_pairwise = pd.concat(
            [wilcoxon_pairs(df_blocks_valid, it) for it in composite_items],
            ignore_index=True,
        )
        comp_desc.to_csv(os.path.join(args.out, "tables", "composite_descriptives.csv"), index=False)
        comp_stats.to_csv(os.path.join(args.out, "tables", "composite_friedman_tests.csv"), index=False)
        comp_pairwise.to_csv(os.path.join(args.out, "tables", "composite_wilcoxon_pairwise.csv"), index=False)

    # Order/learning check: A_4 by block position
    if "A_4" in df_blocks_valid.columns and "block_position" in df_blocks_valid.columns:
        save_boxplot_grouped(
            df_blocks_valid[df_blocks_valid["block_position"].notna()],
            "A_4",
            "block_position",
            "A_4 by block position (learning check)",
            "Likert (1–7)",
            os.path.join(add_fig_dir, "Fig10_A4_by_block_position.eps"),
        )

    # Table figures for CSV outputs (additional folder)
    item_order = {k: i for i, k in enumerate([*A_ITEMS, *B_ITEMS])}
    cond_order = {"A": 0, "B": 1, "C": 2}
    pair_order = {"A-B": 0, "A-C": 1, "B-C": 2}

    if not df_desc.empty:
        df_desc_plot = df_desc.copy()
        df_desc_plot["item_order"] = df_desc_plot["item"].map(item_order)
        df_desc_plot["cond_order"] = df_desc_plot["condition"].map(cond_order)
        df_desc_plot = df_desc_plot.sort_values(["item_order", "cond_order"])
        df_desc_plot = df_desc_plot.drop(columns=["item_order", "cond_order"])
        save_table_figure(
            df_desc_plot,
            ["item", "condition", "n", "mean", "sd", "median", "iqr"],
            os.path.join(add_fig_dir, "Table01_likert_descriptives.eps"),
            title="Likert descriptives by item and condition",
        )

    if not df_stats.empty:
        df_stats_plot = df_stats.copy()
        df_stats_plot["item_order"] = df_stats_plot["item"].map(item_order)
        df_stats_plot = df_stats_plot.sort_values(["item_order"])
        df_stats_plot = df_stats_plot.drop(columns=["item_order"])
        save_table_figure(
            df_stats_plot,
            ["item", "n", "chi2", "p", "kendalls_w"],
            os.path.join(add_fig_dir, "Table02_friedman_tests.eps"),
            title="Friedman tests (A_1–A_7, B_1–B_12)",
            max_rows=32,
        )

    if not df_pairwise.empty:
        df_pairwise_plot = df_pairwise.copy()
        df_pairwise_plot["item_order"] = df_pairwise_plot["item"].map(item_order)
        df_pairwise_plot["pair_order"] = df_pairwise_plot["pair"].map(pair_order)
        df_pairwise_plot = df_pairwise_plot.sort_values(["item_order", "pair_order"])
        df_pairwise_plot = df_pairwise_plot.drop(columns=["item_order", "pair_order"])
        save_table_figure(
            df_pairwise_plot,
            ["item", "pair", "n", "stat", "p", "p_holm"],
            os.path.join(add_fig_dir, "Table03_wilcoxon_pairwise.eps"),
            title="Wilcoxon pairwise tests with Holm correction",
            max_rows=30,
        )

    if df_param_counts is not None and not df_param_counts.empty:
        df_param_plot = df_param_counts.copy()
        df_param_plot["cond_order"] = df_param_plot["condition"].map(cond_order)
        df_param_plot = df_param_plot.sort_values(["cond_order", "count"], ascending=[True, False])
        df_param_plot = df_param_plot.drop(columns=["cond_order"])
        save_table_figure(
            df_param_plot,
            ["condition", "param", "count"],
            os.path.join(add_fig_dir, "Table04_param_influence_counts.eps"),
            title="Parameter influence counts by condition",
        )

    # Composite tables (if generated)
    if composite_items:
        comp_desc_plot = comp_desc.copy()
        comp_desc_plot["item_order"] = comp_desc_plot["item"].map({k: i for i, k in enumerate(composite_items)})
        comp_desc_plot["cond_order"] = comp_desc_plot["condition"].map(cond_order)
        comp_desc_plot = comp_desc_plot.sort_values(["item_order", "cond_order"])
        comp_desc_plot = comp_desc_plot.drop(columns=["item_order", "cond_order"])
        save_table_figure(
            comp_desc_plot,
            ["item", "condition", "n", "mean", "sd", "median", "iqr"],
            os.path.join(add_fig_dir, "Table05_composite_descriptives.eps"),
            title="Composite index descriptives by condition",
        )

        save_table_figure(
            comp_stats,
            ["item", "n", "chi2", "p", "kendalls_w"],
            os.path.join(add_fig_dir, "Table06_composite_friedman_tests.eps"),
            title="Composite indices: Friedman tests",
        )

        save_table_figure(
            comp_pairwise,
            ["item", "pair", "n", "stat", "p", "p_holm"],
            os.path.join(add_fig_dir, "Table07_composite_wilcoxon_pairwise.eps"),
            title="Composite indices: Wilcoxon pairwise tests",
        )

    # -------------------------
    # Addendum: export raw to CSV
    # -------------------------
    if args.addendum:
        with open(args.addendum, "r", encoding="utf-8") as f:
            add_json = json.load(f)
        add_rows = []
        for d in iter_dicts(add_json):
            pid = find_first(d, PID_KEYS)
            if isinstance(pid, (int, float)):
                pid = str(pid)
            if isinstance(pid, str):
                pid = pid.strip()
            ans = extract_answers_block(d)
            # If it contains any non-empty answers, store it.
            if pid and (len(ans) > 0 or any(k in d for k in ["title", "context", "add", "remove", "authorship"])):
                row = {"participant_id": pid}
                # Keep all scalar keys (best-effort)
                for k, v in d.items():
                    if isinstance(v, (str, int, float, bool)) and k not in SECTION_KEYS and k not in TS_KEYS:
                        row[k] = v
                # Merge extracted answers
                row.update(ans)
                add_rows.append(row)
        df_add = pd.DataFrame(add_rows).drop_duplicates()
        df_add.to_csv(os.path.join(args.out, "tables", "addendum_raw.csv"), index=False)

    # -------------------------
    # Save log
    # -------------------------
    with open(os.path.join(args.out, "log.txt"), "w", encoding="utf-8") as f:
        for line in log_lines:
            f.write(line + "\n")

    print("Done.")
    print(f"Figures: {args.fig}/core and {args.fig}/additional")
    print(f"Tables + summaries: {args.out}/")


if __name__ == "__main__":
    main()
