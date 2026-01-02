#!/usr/bin/env python3
"""
make_results.py — TZ5 Audiovisual Intermediality Study
------------------------------------------------------

Purpose
- Generate Organised Sound–ready results tables and figures from:
    (1) participant survey responses (solo + dyad)
    (2) external rater survey responses
    (3) clip manifest linking recordings ↔ conditions ↔ participants

What this script assumes
- Exports are available at:
    Participant Survey/exports/sections.csv
    Rater Survey/exports/ratings.csv
    Rater Survey/clips/manifest.csv
  (override with CLI flags if needed).

Outputs (default ./out/)
- tables/
    Table1_participants.csv
    Table2_clips_and_raters.csv
    Pairwise_differences_participants.csv
- figures/ (EPS + PNG previews)
    F2_participant_ratings_by_condition.eps/.png
    F3_rater_ratings_by_condition.eps/.png
    F4_interference_profile.eps/.png
    F5_self_other_alignment_fusion.eps/.png
- results_snippets/
    results_summary.txt

Selective runs
- Use --participants-only or --raters-only to scope outputs.

Dependencies
- pandas, numpy, matplotlib
(Optionally) scipy for confidence ellipses; script falls back if missing.

OS note
- Graphs are saved as EPS (vector) for line-art suitability.

Author: generated with ChatGPT. You should cite/acknowledge appropriately if required by your institution/journal.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# -----------------------------
# Configuration (edit as needed)
# -----------------------------

@dataclass(frozen=True)
class Config:
    # Condition labels used throughout analysis/figures (edit to match your exports)
    conditions_order: Tuple[str, ...] = ("V", "A", "AV", "DYAD")

    # Human-friendly names for plots/tables
    condition_labels: Dict[str, str] = None

    # Primary constructs (edit to match your questionnaire keys)
    constructs_order: Tuple[str, ...] = (
        "preference",
        "coherence",
        "novelty",
        "fusion",
        "constructive",
        "destructive",
        "overload",
        "agency",
    )

    construct_labels: Dict[str, str] = None

    # Which construct to use for self–other alignment figure
    alignment_construct: str = "fusion"

    # Interference profile axes
    interference_x: str = "constructive"
    interference_y: str = "destructive"

    # Bootstrap settings (fast enough for iterative use)
    bootstrap_n: int = 4000
    ci_alpha: float = 0.05  # 95% CI

    # Minimum number of rater responses for a clip to be included (clip-level aggregation)
    min_raters_per_clip: int = 1

    # EPS/Png export
    fig_dpi_png: int = 200

    # Expected column names (edit to match your data)
    participant_id_col: str = "participant_code"
    condition_col: str = "condition"
    clip_id_col: str = "clip_id"

    # Participant long-format fields:
    # one row per (participant, condition, clip_id?, construct)
    participant_construct_col: str = "construct"
    participant_score_col: str = "score"

    # Rater long-format fields:
    # one row per (token/rater_id, clip_id, construct)
    rater_id_col: str = "token"
    rater_construct_col: str = "construct"
    rater_score_col: str = "score"

    # Rater export may include JSON payload in a single column; if so, parse it first
    rater_payload_col: str = "payload_json"


def default_config() -> Config:
    cond_labels = {
        "V": "Visual-only",
        "A": "Audio-only",
        "AV": "Audiovisual",
        "DYAD": "Dyad (split)",
    }
    construct_labels = {
        "preference": "Preference",
        "coherence": "Coherence",
        "novelty": "Novelty",
        "fusion": "Fusion / Equality",
        "constructive": "Constructive interference",
        "destructive": "Destructive interference",
        "overload": "Overload",
        "agency": "Agency / steerability",
    }
    return Config(condition_labels=cond_labels, construct_labels=construct_labels)


# -----------------------------
# Local data paths (CLI overrides)
# -----------------------------

DEFAULT_PARTICIPANT_CSV = Path("Participant Survey/exports/sections.csv")
DEFAULT_RATER_CSV = Path("Rater Survey/exports/ratings.csv")
DEFAULT_MANIFEST_CSV = Path("Rater Survey/clips/manifest.csv")

PARTICIPANT_CSV_PATH = DEFAULT_PARTICIPANT_CSV
RATER_CSV_PATH = DEFAULT_RATER_CSV
MANIFEST_CSV_PATH = DEFAULT_MANIFEST_CSV

# Mappings from survey payload keys to constructs
PARTICIPANT_BLOCK_CONDITIONS = {"A": "V", "B": "A", "C": "AV"}
PARTICIPANT_PRE_MAP = {
    "preference": "A_1",
    "novelty": "A_5",
    "agency": "A_3",
}
PARTICIPANT_POST_MAP = {
    "fusion": "B_1",
    "coherence": "B_3",
    "constructive": "B_4",
    "destructive": "B_5",
    "overload": "B_6",
}
DYAD_MAP = {
    "preference": "D_8",
    "coherence": "D_7",
    "fusion": "D_6",
}
RATER_PAYLOAD_MAP = {
    "R_1": "preference",
    "R_2": "coherence",
    "R_3": "novelty",
    "R_4": "fusion",
    "R_5": "constructive",
    "R_6": "destructive",
    "R_7": "overload",
    "R_9": "agency",
}

# -----------------------------
# Data loading (from survey exports)
# -----------------------------

def load_participant_df(cfg: Config) -> pd.DataFrame:
    """
    Return a *long-format* participant dataframe with at least:
      - participant_code
      - condition   (one of cfg.conditions_order)
      - construct   (one of cfg.constructs_order)
      - score       (numeric Likert, typically 1..7)
    Optional but recommended:
      - clip_id     (so we can link to rater means precisely)
      - musical_experience, generative_familiarity, etc. for Table 1

    Example shape (first rows):
      participant_code | condition | clip_id | construct | score
      9746T            | AV        | 12      | fusion    | 6
    """
    path = PARTICIPANT_CSV_PATH
    if not path.exists():
        raise FileNotFoundError(f"Participant export not found: {path}")

    raw = pd.read_csv(path)
    required = {"participant_id", "section_key", "payload_json"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Participant export missing columns: {sorted(missing)}")

    sections_by_pid: Dict[str, Dict[str, dict]] = {}
    for _, row in raw.iterrows():
        pid = str(row.get("participant_id", "")).strip()
        if not pid:
            continue
        section_key = str(row.get("section_key", "")).strip()
        payload = parse_payload_cell(row.get("payload_json"))
        sections_by_pid.setdefault(pid, {})[section_key] = payload or {}

    rows: List[dict] = []
    meta_rows: List[dict] = []
    for pid, sections in sections_by_pid.items():
        bg = sections.get("background", {}) if isinstance(sections.get("background", {}), dict) else {}
        meta_rows.append({
            cfg.participant_id_col: pid,
            "age_band": bg.get("age_range"),
            "musical_experience": bg.get("musical_experience"),
            "generative_familiarity": bg.get("generative_experience"),
        })

        for block_code, condition in PARTICIPANT_BLOCK_CONDITIONS.items():
            pre = sections.get(f"block_{block_code}_pre", {})
            post = sections.get(f"block_{block_code}_post", {})
            if not isinstance(pre, dict):
                pre = {}
            if not isinstance(post, dict):
                post = {}

            for construct, key in PARTICIPANT_PRE_MAP.items():
                value = pre.get(key)
                if value not in (None, ""):
                    rows.append({
                        cfg.participant_id_col: pid,
                        cfg.condition_col: condition,
                        cfg.participant_construct_col: construct,
                        cfg.participant_score_col: value,
                    })

            for construct, key in PARTICIPANT_POST_MAP.items():
                value = post.get(key)
                if value not in (None, ""):
                    rows.append({
                        cfg.participant_id_col: pid,
                        cfg.condition_col: condition,
                        cfg.participant_construct_col: construct,
                        cfg.participant_score_col: value,
                    })

        dyad = sections.get("dyad", {})
        if isinstance(dyad, dict):
            for construct, key in DYAD_MAP.items():
                value = dyad.get(key)
                if value not in (None, ""):
                    rows.append({
                        cfg.participant_id_col: pid,
                        cfg.condition_col: "DYAD",
                        cfg.participant_construct_col: construct,
                        cfg.participant_score_col: value,
                    })

    if not rows:
        return pd.DataFrame(columns=[cfg.participant_id_col, cfg.condition_col, cfg.participant_construct_col, cfg.participant_score_col])

    df = pd.DataFrame(rows)
    meta_df = pd.DataFrame(meta_rows).drop_duplicates(subset=[cfg.participant_id_col])
    return df.merge(meta_df, on=cfg.participant_id_col, how="left")


def load_rater_df(cfg: Config) -> pd.DataFrame:
    """
    Return a *long-format* rater dataframe with at least:
      - token (or another rater_id)
      - clip_id
      - construct
      - score
    If you only have an export where the ratings live inside JSON payload, you can:
      - return the raw dataframe and call parse_rater_payload_wide_to_long() yourself, OR
      - adapt parse_rater_payload_wide_to_long() below.

    Example:
      token | clip_id | construct | score
      abcd  | 12      | fusion    | 5
    """
    path = RATER_CSV_PATH
    if not path.exists():
        raise FileNotFoundError(f"Rater export not found: {path}")

    raw = pd.read_csv(path)
    required = {"token", "clip_id", "payload_json"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Rater export missing columns: {sorted(missing)}")

    rows: List[dict] = []
    for _, row in raw.iterrows():
        token = row.get("token")
        clip_id = row.get("clip_id")
        payload = parse_payload_cell(row.get("payload_json"))
        if payload is None or not isinstance(payload, dict):
            continue
        for payload_key, construct in RATER_PAYLOAD_MAP.items():
            if payload_key not in payload:
                continue
            value = payload.get(payload_key)
            if value in (None, ""):
                continue
            rows.append({
                cfg.rater_id_col: token,
                cfg.clip_id_col: clip_id,
                cfg.rater_construct_col: construct,
                cfg.rater_score_col: value,
            })

    if not rows:
        return pd.DataFrame(columns=[cfg.rater_id_col, cfg.clip_id_col, cfg.rater_construct_col, cfg.rater_score_col])
    return pd.DataFrame(rows)


def load_manifest_df(cfg: Config) -> pd.DataFrame:
    """
    Return clip manifest with at least:
      - clip_id
      - condition  (V/A/AV/DYAD)
    Strongly recommended:
      - participant_code
      - role (dyad_audio / dyad_visual), preset_id, timestamp, filepath

    Example:
      clip_id | participant_code | condition | role | preset_id | filepath
      12      | 9746T            | AV        | solo | S0_end    | ...
    """
    path = MANIFEST_CSV_PATH
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    df = pd.read_csv(path)
    return df


# -----------------------------
# Utilities
# -----------------------------

def ensure_dirs(outdir: Path) -> Dict[str, Path]:
    figs = outdir / "figures"
    tabs = outdir / "tables"
    snip = outdir / "results_snippets"
    figs.mkdir(parents=True, exist_ok=True)
    tabs.mkdir(parents=True, exist_ok=True)
    snip.mkdir(parents=True, exist_ok=True)
    return {"figures": figs, "tables": tabs, "snippets": snip}


def coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def bootstrap_ci_mean(values: np.ndarray, n: int, alpha: float, rng: np.random.Generator) -> Tuple[float, float, float]:
    """
    Bootstrap CI for the mean. Returns (mean, lo, hi).
    """
    values = values[np.isfinite(values)]
    if values.size == 0:
        return (np.nan, np.nan, np.nan)
    mu = float(values.mean())
    idx = rng.integers(0, values.size, size=(n, values.size))
    boots = values[idx].mean(axis=1)
    lo = float(np.quantile(boots, alpha / 2))
    hi = float(np.quantile(boots, 1 - alpha / 2))
    return (mu, lo, hi)


def bootstrap_ci_mean_paired_diff(
    a: np.ndarray, b: np.ndarray, n: int, alpha: float, rng: np.random.Generator
) -> Tuple[float, float, float]:
    """
    Bootstrap CI for mean paired difference (a - b).
    Inputs must be aligned arrays of equal length (one per participant).
    Returns (diff_mean, lo, hi).
    """
    mask = np.isfinite(a) & np.isfinite(b)
    a2, b2 = a[mask], b[mask]
    if a2.size == 0:
        return (np.nan, np.nan, np.nan)
    d = a2 - b2
    dm = float(d.mean())
    idx = rng.integers(0, d.size, size=(n, d.size))
    boots = d[idx].mean(axis=1)
    lo = float(np.quantile(boots, alpha / 2))
    hi = float(np.quantile(boots, 1 - alpha / 2))
    return (dm, lo, hi)


def save_fig(fig: plt.Figure, basepath: Path, dpi_png: int) -> None:
    fig.savefig(str(basepath.with_suffix(".eps")), format="eps", bbox_inches="tight")
    fig.savefig(str(basepath.with_suffix(".png")), dpi=dpi_png, bbox_inches="tight")
    plt.close(fig)


def safe_spearman(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """
    Returns (rho, approx_p) using scipy if available; otherwise rho only with p=nan.
    """
    mask = np.isfinite(x) & np.isfinite(y)
    x2, y2 = x[mask], y[mask]
    if x2.size < 3:
        return (np.nan, np.nan)
    try:
        from scipy.stats import spearmanr  # type: ignore
        r, p = spearmanr(x2, y2)
        return (float(r), float(p))
    except Exception:
        # Fallback: compute rho by rank correlation (no p-value)
        rx = pd.Series(x2).rank().to_numpy()
        ry = pd.Series(y2).rank().to_numpy()
        r = np.corrcoef(rx, ry)[0, 1]
        return (float(r), np.nan)


def confidence_ellipse_params(x: np.ndarray, y: np.ndarray, n_std: float = 2.0) -> Optional[Tuple[float, float, float, float, float]]:
    """
    Returns (mean_x, mean_y, width, height, angle_deg) for an ellipse.
    n_std=2 approximates ~95% for normal data.
    """
    mask = np.isfinite(x) & np.isfinite(y)
    x2, y2 = x[mask], y[mask]
    if x2.size < 3:
        return None
    cov = np.cov(x2, y2)
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    angle = math.degrees(math.atan2(*vecs[:, 0][::-1]))
    width, height = 2 * n_std * np.sqrt(vals)
    return (float(x2.mean()), float(y2.mean()), float(width), float(height), float(angle))


# -----------------------------
# Optional: parsing helper for rater exports
# -----------------------------

def parse_payload_cell(cell) -> Optional[dict]:
    if cell is None or (isinstance(cell, float) and np.isnan(cell)):
        return None
    if isinstance(cell, dict):
        return cell
    if isinstance(cell, str):
        s = cell.strip()
        if not s:
            return None
        # Try JSON, then Python literal
        try:
            return json.loads(s)
        except Exception:
            try:
                return ast.literal_eval(s)
            except Exception:
                return None
    return None


def rater_payload_wide_to_long(
    rater_raw: pd.DataFrame,
    cfg: Config,
    *,
    token_col: Optional[str] = None,
    clip_id_col: Optional[str] = None,
    payload_col: Optional[str] = None,
    mapping: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Convert a rater export where the Likerts are inside a JSON payload into long format.

    - mapping: maps payload keys -> construct names (cfg.constructs_order)
      Example: {"R_4": "fusion", "R_5":"constructive", ...}

    Returns:
      token | clip_id | construct | score
    """
    token_col = token_col or cfg.rater_id_col
    clip_id_col = clip_id_col or cfg.clip_id_col
    payload_col = payload_col or cfg.rater_payload_col
    mapping = mapping or {}

    rows = []
    for _, row in rater_raw.iterrows():
        token = row.get(token_col, None)
        clip_id = row.get(clip_id_col, None)
        payload = parse_payload_cell(row.get(payload_col, None))
        if payload is None:
            continue
        for payload_key, construct in mapping.items():
            if payload_key in payload:
                try:
                    score = float(payload[payload_key])
                except Exception:
                    continue
                rows.append({cfg.rater_id_col: token, cfg.clip_id_col: clip_id, cfg.rater_construct_col: construct, cfg.rater_score_col: score})
    return pd.DataFrame(rows)


# -----------------------------
# Core transformations
# -----------------------------

def make_table1_participants(participant_df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    Table 1: Participant characteristics
    This function is deliberately conservative: it only reports columns that exist.
    """
    pid = cfg.participant_id_col
    base = participant_df[[pid]].drop_duplicates().copy()
    base["n_blocks"] = participant_df.groupby(pid).size().reindex(base[pid].values).values

    # Optional columns to summarise if present
    optional_cols = ["musical_experience", "generative_familiarity", "age_band"]
    for c in optional_cols:
        if c in participant_df.columns:
            # take first non-null per participant
            base[c] = participant_df.groupby(pid)[c].apply(lambda s: s.dropna().iloc[0] if s.dropna().shape[0] else np.nan).values

    return base.sort_values(pid).reset_index(drop=True)


def condition_construct_summary(
    df_long: pd.DataFrame,
    cfg: Config,
    *,
    unit: str,
    aggregate_unit_first: bool,
    unit_id_col: str,
    condition_col: str,
    construct_col: str,
    score_col: str,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Summarise mean and bootstrap CI by condition and construct.
    If aggregate_unit_first=True, compute unit-level means first (e.g., per clip), then bootstrap across units.
    """
    d = df_long.copy()
    d[score_col] = coerce_numeric(d[score_col])

    if aggregate_unit_first:
        # average within unit for each condition/construct
        d = (
            d.groupby([unit_id_col, condition_col, construct_col], as_index=False)[score_col]
            .mean()
        )

    out_rows = []
    for cond in cfg.conditions_order:
        for constr in cfg.constructs_order:
            sub = d[(d[condition_col] == cond) & (d[construct_col] == constr)][score_col].to_numpy(dtype=float)
            mu, lo, hi = bootstrap_ci_mean(sub, cfg.bootstrap_n, cfg.ci_alpha, rng)
            out_rows.append({
                "unit": unit,
                "condition": cond,
                "construct": constr,
                "mean": mu,
                "ci_lo": lo,
                "ci_hi": hi,
                "n": int(np.isfinite(sub).sum()),
            })
    return pd.DataFrame(out_rows)


def participant_pairwise_differences(participant_df: pd.DataFrame, cfg: Config, rng: np.random.Generator) -> pd.DataFrame:
    """
    Paired differences for participants: AV - A, AV - V, etc. by construct.
    Requires participant_df to contain participant means per condition/construct.
    """
    pid = cfg.participant_id_col
    cond = cfg.condition_col
    constr = cfg.participant_construct_col
    score = cfg.participant_score_col

    # unit = participant; ensure one row per participant-condition-construct by averaging (safe)
    d = participant_df.copy()
    d[score] = coerce_numeric(d[score])
    d = d.groupby([pid, cond, constr], as_index=False)[score].mean()

    def pivot(cond_code: str, construct: str) -> pd.Series:
        s = d[(d[cond] == cond_code) & (d[constr] == construct)].set_index(pid)[score]
        return s

    pairs = [("AV", "A"), ("AV", "V"), ("AV", "DYAD"), ("A", "V")]
    rows = []
    for a, b in pairs:
        if a not in cfg.conditions_order or b not in cfg.conditions_order:
            continue
        for c in cfg.constructs_order:
            sa = pivot(a, c)
            sb = pivot(b, c)
            # align
            idx = sa.index.union(sb.index)
            aa = sa.reindex(idx).to_numpy(dtype=float)
            bb = sb.reindex(idx).to_numpy(dtype=float)
            dm, lo, hi = bootstrap_ci_mean_paired_diff(aa, bb, cfg.bootstrap_n, cfg.ci_alpha, rng)
            rows.append({
                "comparison": f"{a} - {b}",
                "construct": c,
                "diff_mean": dm,
                "ci_lo": lo,
                "ci_hi": hi,
                "n": int(np.isfinite(aa).sum() & np.isfinite(bb).sum()) if False else int(np.isfinite(aa).sum()),
            })
    return pd.DataFrame(rows)


def clip_level_rater_means(rater_df: pd.DataFrame, manifest_df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """
    Aggregate rater scores to clip means per construct (reduces pseudo-replication),
    then join condition from manifest.

    Returns:
      clip_id | condition | construct | clip_mean | n_raters
    """
    d = rater_df.copy()
    d[cfg.rater_score_col] = coerce_numeric(d[cfg.rater_score_col])

    # clip-construct mean, count raters
    agg = (
        d.groupby([cfg.clip_id_col, cfg.rater_construct_col], as_index=False)
        .agg(
            clip_mean=(cfg.rater_score_col, "mean"),
            n_raters=(cfg.rater_score_col, lambda s: int(np.isfinite(pd.to_numeric(s, errors="coerce")).sum())),
        )
    )

    # apply min raters filter
    agg = agg[agg["n_raters"] >= cfg.min_raters_per_clip].copy()

    # join condition
    m = manifest_df[[cfg.clip_id_col, cfg.condition_col]].drop_duplicates()
    out = agg.merge(m, how="left", on=cfg.clip_id_col)
    return out


# -----------------------------
# Figure builders
# -----------------------------

def fig_condition_construct_means(
    summary_df: pd.DataFrame,
    cfg: Config,
    title: str,
    *,
    outfile: Path,
) -> None:
    """
    A compact “constructs x conditions” plot: each construct is a row, conditions are points with CI.
    """
    # Layout
    constructs = list(cfg.constructs_order)
    conditions = list(cfg.conditions_order)

    # Prepare plot
    fig_h = max(4.5, 0.45 * len(constructs) + 1.2)
    fig = plt.figure(figsize=(10, fig_h))
    ax = fig.add_subplot(111)

    # Y positions per construct
    y = np.arange(len(constructs))[::-1]  # top to bottom
    y_map = {c: y[i] for i, c in enumerate(constructs)}

    # Small x offsets to avoid overlap
    offsets = np.linspace(-0.18, 0.18, num=len(conditions))

    for j, cond in enumerate(conditions):
        sub = summary_df[summary_df["condition"] == cond]
        for i, constr in enumerate(constructs):
            row = sub[sub["construct"] == constr]
            if row.empty:
                continue
            mu = float(row["mean"].iloc[0])
            lo = float(row["ci_lo"].iloc[0])
            hi = float(row["ci_hi"].iloc[0])

            ax.errorbar(
                mu,
                y_map[constr] + offsets[j],
                xerr=[[mu - lo], [hi - mu]],
                fmt="o",
                capsize=3,
                markersize=4,
                linewidth=1,
                label=cfg.condition_labels.get(cond, cond) if i == 0 else None,
            )

    ax.set_yticks(list(y_map.values()))
    ax.set_yticklabels([cfg.construct_labels.get(c, c) for c in constructs])
    ax.set_xlabel("Mean rating (1–7)")
    ax.set_title(title)
    ax.set_xlim(1, 7)
    ax.grid(True, axis="x", alpha=0.25)
    ax.legend(loc="lower right", frameon=True)

    save_fig(fig, outfile, cfg.fig_dpi_png)


def fig_interference_profile(
    participant_df: pd.DataFrame,
    rater_clip_means_df: pd.DataFrame,
    cfg: Config,
    *,
    outfile: Path,
) -> None:
    """
    2D plot of condition means in (constructive, destructive) space, with rough confidence ellipses.
    Uses participant unit-level means for solo (participants) and clip-level means for rater aggregation.
    """
    xk, yk = cfg.interference_x, cfg.interference_y

    # Prepare participant unit means (participant-level)
    p = participant_df.copy()
    p[cfg.participant_score_col] = coerce_numeric(p[cfg.participant_score_col])
    p = p.groupby([cfg.participant_id_col, cfg.condition_col, cfg.participant_construct_col], as_index=False)[cfg.participant_score_col].mean()
    p_wide = p.pivot_table(
        index=[cfg.participant_id_col, cfg.condition_col],
        columns=cfg.participant_construct_col,
        values=cfg.participant_score_col,
        aggfunc="mean",
    ).reset_index()

    # Prepare rater clip means (clip-level)
    r = rater_clip_means_df.copy()
    r_wide = r.pivot_table(
        index=[cfg.clip_id_col, cfg.condition_col],
        columns="construct",
        values="clip_mean",
        aggfunc="mean",
    ).reset_index()

    fig = plt.figure(figsize=(8.5, 6.5))
    ax = fig.add_subplot(111)

    for cond in cfg.conditions_order:
        # Participants
        ps = p_wide[p_wide[cfg.condition_col] == cond]
        if xk in ps.columns and yk in ps.columns and ps.shape[0] >= 3:
            x = ps[xk].to_numpy(dtype=float)
            y = ps[yk].to_numpy(dtype=float)
            ax.scatter(x, y, s=18, alpha=0.25, marker="o")
            ell = confidence_ellipse_params(x, y, n_std=2.0)
            if ell is not None:
                mx, my, w, h, ang = ell
                try:
                    from matplotlib.patches import Ellipse
                    e = Ellipse((mx, my), w, h, angle=ang, fill=False, linewidth=1)
                    ax.add_patch(e)
                except Exception:
                    pass
                ax.plot([mx], [my], marker="o", markersize=6, label=f"{cfg.condition_labels.get(cond, cond)} (participants)")

        # Raters (clip means)
        rs = r_wide[r_wide[cfg.condition_col] == cond]
        if xk in rs.columns and yk in rs.columns and rs.shape[0] >= 3:
            x = rs[xk].to_numpy(dtype=float)
            y = rs[yk].to_numpy(dtype=float)
            ax.scatter(x, y, s=22, alpha=0.35, marker="x")
            ell = confidence_ellipse_params(x, y, n_std=2.0)
            if ell is not None:
                mx, my, w, h, ang = ell
                try:
                    from matplotlib.patches import Ellipse
                    e = Ellipse((mx, my), w, h, angle=ang, fill=False, linewidth=1, linestyle="--")
                    ax.add_patch(e)
                except Exception:
                    pass
                ax.plot([mx], [my], marker="x", markersize=7, label=f"{cfg.condition_labels.get(cond, cond)} (raters)")

    ax.set_xlabel(cfg.construct_labels.get(xk, xk) + " (1–7)")
    ax.set_ylabel(cfg.construct_labels.get(yk, yk) + " (1–7)")
    ax.set_title("Intermedial interference profile (constructive vs destructive)")
    ax.set_xlim(1, 7)
    ax.set_ylim(1, 7)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=8, frameon=True)

    save_fig(fig, outfile, cfg.fig_dpi_png)


def fig_self_other_alignment(
    participant_df: pd.DataFrame,
    rater_clip_means_df: pd.DataFrame,
    manifest_df: pd.DataFrame,
    cfg: Config,
    *,
    outfile: Path,
) -> Tuple[float, float, int]:
    """
    Scatter plot: participant self-rating vs rater mean for the same clip (alignment_construct).
    Returns (rho, p, n_pairs).
    """
    k = cfg.alignment_construct

    # Participant: need clip_id to join. If participant_df lacks clip_id, attempt to join via manifest
    p = participant_df.copy()
    if cfg.clip_id_col not in p.columns:
        # try to join using participant_code + condition
        if cfg.participant_id_col in manifest_df.columns and cfg.condition_col in manifest_df.columns:
            join_cols = [cfg.participant_id_col, cfg.condition_col]
            m = manifest_df[[cfg.clip_id_col] + join_cols].drop_duplicates()
            p = p.merge(m, how="left", on=join_cols)
        else:
            raise ValueError("Participant DF has no clip_id, and manifest lacks participant_code/condition to infer it.")

    p = p[p[cfg.participant_construct_col] == k].copy()
    p[cfg.participant_score_col] = coerce_numeric(p[cfg.participant_score_col])
    p = p.groupby([cfg.clip_id_col], as_index=False)[cfg.participant_score_col].mean().rename(columns={cfg.participant_score_col: "participant_mean"})

    # Rater: clip mean for construct
    r = rater_clip_means_df[rater_clip_means_df["construct"] == k].copy()
    r = r.groupby([cfg.clip_id_col], as_index=False).agg(rater_mean=("clip_mean", "mean"), n_raters=("n_raters", "mean"))

    d = p.merge(r, how="inner", on=cfg.clip_id_col)
    x = d["participant_mean"].to_numpy(dtype=float)
    y = d["rater_mean"].to_numpy(dtype=float)

    rho, pval = safe_spearman(x, y)

    fig = plt.figure(figsize=(7.0, 6.0))
    ax = fig.add_subplot(111)
    ax.scatter(x, y, s=28, alpha=0.8)
    ax.set_xlabel(f"Participant self-rating: {cfg.construct_labels.get(k, k)} (clip mean)")
    ax.set_ylabel(f"External rater rating: {cfg.construct_labels.get(k, k)} (clip mean)")
    ax.set_title(f"Self–other alignment ({cfg.construct_labels.get(k, k)}): Spearman ρ={rho:.2f}")
    ax.set_xlim(1, 7)
    ax.set_ylim(1, 7)
    ax.grid(True, alpha=0.25)

    save_fig(fig, outfile, cfg.fig_dpi_png)

    return rho, pval, int(d.shape[0])


# -----------------------------
# Main orchestration
# -----------------------------

def run(
    cfg: Config,
    outdir: Path,
    seed: int = 123,
    *,
    include_participants: bool = True,
    include_raters: bool = True,
) -> None:
    paths = ensure_dirs(outdir)
    rng = np.random.default_rng(seed)

    # Load data
    participant_df = load_participant_df(cfg) if include_participants else None
    rater_df = load_rater_df(cfg) if include_raters else None
    manifest_df = load_manifest_df(cfg) if include_raters else None

    # Basic sanity
    required_p = {cfg.participant_id_col, cfg.condition_col, cfg.participant_construct_col, cfg.participant_score_col}
    required_r = {cfg.rater_id_col, cfg.clip_id_col, cfg.rater_construct_col, cfg.rater_score_col}
    required_m = {cfg.clip_id_col, cfg.condition_col}

    summary_lines = []
    summary_lines.append("RESULTS SUMMARY (AUTO-GENERATED)\n")

    t1 = None
    p_summary = None
    tdiff = None
    r_clip = None
    t2 = None
    r_summary = None
    rho = pval = np.nan
    n_pairs = 0

    if include_participants and participant_df is not None:
        missing = required_p - set(participant_df.columns)
        if missing:
            raise ValueError(f"Participant DF missing columns: {sorted(missing)}")

        t1 = make_table1_participants(participant_df, cfg)
        t1.to_csv(paths["tables"] / "Table1_participants.csv", index=False)

        p_summary = condition_construct_summary(
            participant_df,
            cfg,
            unit="participant",
            aggregate_unit_first=True,
            unit_id_col=cfg.participant_id_col,
            condition_col=cfg.condition_col,
            construct_col=cfg.participant_construct_col,
            score_col=cfg.participant_score_col,
            rng=rng,
        )

        fig_condition_construct_means(
            p_summary,
            cfg,
            title="Participant self-ratings by condition (mean ± 95% CI)",
            outfile=paths["figures"] / "F2_participant_ratings_by_condition",
        )

        tdiff = participant_pairwise_differences(participant_df, cfg, rng)
        tdiff.to_csv(paths["tables"] / "Pairwise_differences_participants.csv", index=False)

        summary_lines.append(f"Participants: n={t1.shape[0]} unique.\n")
        summary_lines.append("\nPrimary participant summaries (mean±CI):\n")
        summary_lines.append(p_summary.to_string(index=False))
        summary_lines.append("\n\nPairwise participant differences (bootstrap CI):\n")
        summary_lines.append(tdiff.to_string(index=False))

    if include_raters and rater_df is not None:
        missing = required_r - set(rater_df.columns)
        if missing:
            raise ValueError(f"Rater DF missing columns: {sorted(missing)}")

        if manifest_df is None:
            raise ValueError("Manifest is required for rater results.")

        missing = required_m - set(manifest_df.columns)
        if missing:
            raise ValueError(f"Manifest DF missing columns: {sorted(missing)}")

        r_clip = clip_level_rater_means(rater_df, manifest_df, cfg)

        t2 = (
            r_clip.groupby([cfg.condition_col], as_index=False)
            .agg(
                n_clips=(cfg.clip_id_col, "nunique"),
                median_raters=("n_raters", "median"),
                min_raters=("n_raters", "min"),
                max_raters=("n_raters", "max"),
            )
        )
        m_counts = manifest_df.groupby(cfg.condition_col, as_index=False).agg(n_manifest_clips=(cfg.clip_id_col, "nunique"))
        t2 = m_counts.merge(t2, how="left", on=cfg.condition_col).sort_values(cfg.condition_col)
        t2.to_csv(paths["tables"] / "Table2_clips_and_raters.csv", index=False)

        r_clip_long = r_clip.rename(columns={"clip_mean": "score", "construct": cfg.rater_construct_col})
        r_summary = condition_construct_summary(
            r_clip_long.rename(columns={"score": cfg.rater_score_col}),
            cfg,
            unit="clip",
            aggregate_unit_first=False,
            unit_id_col=cfg.clip_id_col,
            condition_col=cfg.condition_col,
            construct_col=cfg.rater_construct_col,
            score_col=cfg.rater_score_col,
            rng=rng,
        )

        fig_condition_construct_means(
            r_summary,
            cfg,
            title="External rater ratings by condition (clip means ± 95% CI)",
            outfile=paths["figures"] / "F3_rater_ratings_by_condition",
        )

        summary_lines.append("\nRater coverage by condition:\n")
        summary_lines.append(t2.to_string(index=False))
        summary_lines.append("\n\nPrimary rater summaries (mean±CI):\n")
        summary_lines.append(r_summary.to_string(index=False))

    if include_participants and include_raters and participant_df is not None and r_clip is not None and manifest_df is not None:
        fig_interference_profile(
            participant_df=participant_df,
            rater_clip_means_df=r_clip.rename(columns={"construct": "construct", "clip_mean": "clip_mean"}),
            cfg=cfg,
            outfile=paths["figures"] / "F4_interference_profile",
        )

        rho, pval, n_pairs = fig_self_other_alignment(
            participant_df=participant_df,
            rater_clip_means_df=r_clip.rename(columns={"construct": "construct", "clip_mean": "clip_mean"}),
            manifest_df=manifest_df,
            cfg=cfg,
            outfile=paths["figures"] / "F5_self_other_alignment_fusion",
        )

        summary_lines.append("\n\nKey alignment:\n")
        summary_lines.append(f"Self–other alignment ({cfg.alignment_construct}): Spearman rho={rho:.3f}, p={pval if np.isfinite(pval) else 'n/a'}, n_clips={n_pairs}\n")

    (paths["snippets"] / "results_summary.txt").write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"[OK] Wrote tables to: {paths['tables']}")
    print(f"[OK] Wrote figures to: {paths['figures']}")
    print(f"[OK] Wrote snippets to: {paths['snippets']}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=str, default="out", help="Output directory for tables/figures/snippets.")
    ap.add_argument("--seed", type=int, default=123, help="RNG seed for bootstrap reproducibility.")
    ap.add_argument("--participant-csv", type=str, default=str(DEFAULT_PARTICIPANT_CSV), help="Participant export CSV path.")
    ap.add_argument("--rater-csv", type=str, default=str(DEFAULT_RATER_CSV), help="Rater export CSV path.")
    ap.add_argument("--manifest-csv", type=str, default=str(DEFAULT_MANIFEST_CSV), help="Clip manifest CSV path.")
    ap.add_argument("--participants-only", action="store_true", help="Only generate participant-derived outputs.")
    ap.add_argument("--raters-only", action="store_true", help="Only generate rater-derived outputs.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    cfg = default_config()
    if args.participants_only and args.raters_only:
        raise SystemExit("Choose only one of --participants-only or --raters-only.")

    global PARTICIPANT_CSV_PATH, RATER_CSV_PATH, MANIFEST_CSV_PATH
    PARTICIPANT_CSV_PATH = Path(args.participant_csv)
    RATER_CSV_PATH = Path(args.rater_csv)
    MANIFEST_CSV_PATH = Path(args.manifest_csv)

    include_participants = not args.raters_only
    include_raters = not args.participants_only
    if not include_participants and not include_raters:
        raise SystemExit("No outputs selected.")

    run(
        cfg,
        Path(args.outdir),
        seed=args.seed,
        include_participants=include_participants,
        include_raters=include_raters,
    )


if __name__ == "__main__":
    main()
