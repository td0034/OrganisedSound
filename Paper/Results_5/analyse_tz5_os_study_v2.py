#!/usr/bin/env python3
"""
analyse_tz5_os_study_v2.py
=========================

INTENTION
---------
Generate a minimal, qualitatively-led quantitative accompaniment for a 7000-word
Organised Sound results section.

This script focuses on:
  (MANDATORY)
  - Table1: participant overview (context + counterbalancing)
  - Fig1: end-of-session categorical outcomes (best overall, most intermedial, biggest mismatch)
  - Fig2: within-participant paired plot of A3 (control/steering) across conditions
  - Fig3: within-participant paired plot of an Intermediality Index (B1-B6 with reversals)

  (STANDARD OUTPUTS; disable with --no-*)
  - Table2: summary of key Likert items (median/IQR per condition)
  - Fig4: overload (B6) paired plot
  - Fig5: reliance contrast (B11 visual cues vs B12 theory) by condition
  - Fig6: parameter influence salience by condition
  - TIFF: 600 dpi version of every figure alongside EPS+PNG

  (OPTIONAL, toggles)
  - Fig4b: mismatch index (B7/B8-derived) paired plot
  - Stats: Friedman + Wilcoxon with Holm correction for A_1..A_7 and B_1..B_12
  - Fig7: agency index (A2-A4 minus A6) paired plot
  - Fig8: A4 by block position (learning check)

STUDY CONDITION DEFINITIONS
---------------------------
A = Visual-only (no audio during composition; audio revealed afterwards)
B = Audio-only  (no visuals during composition; visuals revealed afterwards)
C = Audio+Visual (both available during composition)

INPUT FORMAT
------------
Single JSON file: list of records with keys:
  participant_id, section_key, payload, updated_at

Where:
  block_*_pre  payload contains A_1..A_7 (Part A; pre-reveal ratings)
  block_*_post payload contains B_1..B_12 (Part B; post-reveal ratings) + param_influence list
  end payload contains rank_A/rank_B/rank_C, biggest_mismatch, most_intermedial, etc.

OUTPUTS
-------
Writes to: <outdir>/tables and <outdir>/figures
EPS + PNG by default; optional TIFF via --tif (600 dpi).
Also writes summary_numbers.json and log.txt to <outdir>.

USAGE
-----
python analyse_tz5_os_study_v2.py --input merged_results.json --outdir ./outputs \
  --make-mismatch \
  --make-stats \
  --make-agency \
  --make-order-check

"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from scipy.stats import friedmanchisquare, wilcoxon
except Exception:
    friedmanchisquare = None
    wilcoxon = None


CONDITION_LABELS = {
    "A": "Visual-only",
    "B": "Audio-only",
    "C": "Audio+Visual",
}
CONDITION_ORDER = ["A", "B", "C"]

PID_KEYS = ["participant_id", "participantId", "participant_code", "participantCode", "pid", "code"]
SECTION_KEYS = ["section_key", "sectionKey", "section", "section_id", "sectionId", "page", "step", "form"]
TS_KEYS = [
    "updated_at", "updatedAt",
    "created_at", "createdAt",
    "timestamp", "saved_at", "savedAt", "time",
]

# --- Item labels (for tables/captions)
A_LABELS = {
    "A_1": "A1 Satisfied with outcome",
    "A_2": "A2 Clear intention",
    "A_3": "A3 Able to steer system",
    "A_4": "A4 Interface workable",
    "A_5": "A5 Useful surprise",
    "A_6": "A6 Frustrating unpredictability",
    "A_7": "A7 Others would find it interesting",
}

B_LABELS = {
    "B_1": "B1 Same underlying process",
    "B_2": "B2 Balanced modalities",
    "B_3": "B3 Coherent/legible relationship",
    "B_4": "B4 Constructive interference",
    "B_5": "B5 Destructive interference",
    "B_6": "B6 Overwhelming/overload",
    "B_7": "B7 Revealed modality matched expectation",
    "B_8": "B8 Revealed modality changed interpretation",
    "B_9": "B9 Plausible causal story",
    "B_10": "B10 Strong system autonomy",
    "B_11": "B11 Relied on visual cues",
    "B_12": "B12 Relied on theory expectations",
}

EXTRA_KEYS = {
    "aim", "strategy", "expectation_vs_outcome", "interference_notes",
    "param_influence", "param_other", "preset_id",
    "rank_A", "rank_B", "rank_C", "most_intermedial", "biggest_mismatch",
    "one_change", "reflection", "session_notes_transcription",
    "session_type", "order", "age_range", "musical_experience",
    "theory_familiarity", "tonnetz_familiarity", "generative_experience",
    "color_deficiency", "light_sensitivity", "perceptual_comments", "dyad_done",
}


def parse_timestamp(record: Dict[str, Any]) -> Optional[datetime]:
    for k in TS_KEYS:
        if k in record:
            v = record.get(k)
            if isinstance(v, (int, float)):
                try:
                    return datetime.fromtimestamp(float(v))
                except Exception:
                    return None
            if isinstance(v, str):
                s = v.strip()
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                try:
                    return datetime.fromisoformat(s)
                except Exception:
                    pass
                for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z",
                            "%Y-%m-%dT%H:%M:%S%z",
                            "%Y-%m-%dT%H:%M:%S.%f",
                            "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(s, fmt)
                    except Exception:
                        pass
    return None


def find_first(obj: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for k in keys:
        if k in obj:
            return obj.get(k)
    return None


def iter_dicts(obj: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_dicts(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from iter_dicts(it)


def extract_answers_block(record: Dict[str, Any]) -> Dict[str, Any]:
    candidates = []
    for key in ["answers", "responses", "response", "data", "fields", "values", "payload"]:
        if key in record:
            candidates.append(record[key])

    out: Dict[str, Any] = {}

    def ingest(obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, dict):
            if ("id" in obj or "qid" in obj or "name" in obj) and ("value" in obj or "answer" in obj or "response" in obj):
                qid = obj.get("id") or obj.get("qid") or obj.get("name")
                val = obj.get("value") if "value" in obj else obj.get("answer") if "answer" in obj else obj.get("response")
                if isinstance(qid, str):
                    out[qid.strip()] = val
            else:
                for k, v in obj.items():
                    if isinstance(k, str) and (k.startswith("A_") or k.startswith("B_") or k in EXTRA_KEYS):
                        out[k.strip()] = v
        elif isinstance(obj, list):
            for it in obj:
                ingest(it)

    for c in candidates:
        ingest(c)

    for k, v in record.items():
        if isinstance(k, str) and (k.startswith("A_") or k.startswith("B_") or k in EXTRA_KEYS):
            out.setdefault(k.strip(), v)

    return out


def extract_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    raw = record.get("payload")
    if isinstance(raw, dict):
        payload.update(raw)
    payload.update(extract_answers_block(record))
    return payload


def load_records(path: str, log_lines: List[str]) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates: List[Dict[str, Any]] = []
    if isinstance(data, list):
        candidates = [d for d in data if isinstance(d, dict)]
    else:
        candidates = [d for d in iter_dicts(data)]

    records: List[Dict[str, Any]] = []
    for d in candidates:
        if not isinstance(d, dict):
            continue
        pid = find_first(d, PID_KEYS) or d.get("participant_id")
        sk = find_first(d, SECTION_KEYS) or d.get("section_key")
        payload = extract_payload(d)
        if pid is None and sk is None and not payload:
            continue

        pid_str = str(pid).strip() if pid is not None else None
        sk_str = str(sk).strip() if sk is not None else None

        rec = {
            "participant_id": pid_str,
            "section_key": sk_str,
            "payload": payload,
        }
        for k in TS_KEYS:
            if k in d:
                rec["updated_at"] = d.get(k)
                break
        records.append(rec)

    log_lines.append(f"Records loaded: {len(records)}")
    return records


def latest_per_participant_section(records: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    latest: Dict[Tuple[str, str], Tuple[Optional[datetime], int, Dict[str, Any]]] = {}
    for idx, r in enumerate(records):
        pid = (r.get("participant_id") or "").strip()
        sk = (r.get("section_key") or "").strip()
        if not pid or not sk:
            continue
        curr_ts = parse_timestamp(r)
        prev = latest.get((pid, sk))
        if prev is None:
            latest[(pid, sk)] = (curr_ts, idx, r)
            continue
        prev_ts, prev_idx, _ = prev
        if curr_ts is not None and (prev_ts is None or curr_ts >= prev_ts):
            latest[(pid, sk)] = (curr_ts, idx, r)
        elif curr_ts is None and prev_ts is None and idx >= prev_idx:
            latest[(pid, sk)] = (curr_ts, idx, r)
    return {k: v[2] for k, v in latest.items()}


def build_tables(records: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      participants_df: one row per participant (meta+background)
      pre_df:  one row per participant per condition (A_1..A_7)  from block_*_pre
      post_df: one row per participant per condition (B_1..B_12) from block_*_post
      end_df:  one row per participant (end section)
      blocks_df: merged pre/post rows (per participant + condition)
    """
    latest = latest_per_participant_section(records)

    meta_rows, bg_rows, end_rows = [], [], []
    pre_rows, post_rows = [], []

    for (pid, sk), rec in latest.items():
        payload = rec.get("payload", {}) or {}

        if sk == "meta":
            meta_rows.append({"participant_id": pid, **payload})
        elif sk == "background":
            bg_rows.append({"participant_id": pid, **payload})
        elif sk == "end":
            end_rows.append({"participant_id": pid, **payload})
        elif sk.startswith("block_") and sk.endswith("_pre"):
            parts = sk.split("_")
            if len(parts) >= 3:
                cond = parts[1].upper()
                row = {"participant_id": pid, "condition": cond, "updated_at": rec.get("updated_at"), **payload}
                pre_rows.append(row)
        elif sk.startswith("block_") and sk.endswith("_post"):
            parts = sk.split("_")
            if len(parts) >= 3:
                cond = parts[1].upper()
                row = {"participant_id": pid, "condition": cond, "updated_at": rec.get("updated_at"), **payload}
                post_rows.append(row)

    meta_df = pd.DataFrame(meta_rows).drop_duplicates(subset=["participant_id"], keep="last")
    bg_df = pd.DataFrame(bg_rows).drop_duplicates(subset=["participant_id"], keep="last")
    end_df = pd.DataFrame(end_rows).drop_duplicates(subset=["participant_id"], keep="last")

    participants_df = pd.merge(meta_df, bg_df, on="participant_id", how="outer", suffixes=("_meta", "_bg"))
    for col in ["participant_id_meta", "participant_id_bg"]:
        if col in participants_df.columns:
            participants_df = participants_df.drop(columns=[col])

    pre_df = pd.DataFrame(pre_rows)
    post_df = pd.DataFrame(post_rows)

    # Normalise conditions
    if not pre_df.empty:
        pre_df["condition"] = pre_df["condition"].astype(str).str.upper()
        pre_df = pre_df[pre_df["condition"].isin(CONDITION_ORDER)].copy()
        pre_df["condition_label"] = pre_df["condition"].map(CONDITION_LABELS)
    if not post_df.empty:
        post_df["condition"] = post_df["condition"].astype(str).str.upper()
        post_df = post_df[post_df["condition"].isin(CONDITION_ORDER)].copy()
        post_df["condition_label"] = post_df["condition"].map(CONDITION_LABELS)

    # Coerce Likert columns to numeric
    for c in [k for k in pre_df.columns if k.startswith("A_")]:
        pre_df[c] = pd.to_numeric(pre_df[c], errors="coerce")
    for c in [k for k in post_df.columns if k.startswith("B_")]:
        post_df[c] = pd.to_numeric(post_df[c], errors="coerce")

    # End ranks numeric
    for c in ["rank_A", "rank_B", "rank_C"]:
        if c in end_df.columns:
            end_df[c] = pd.to_numeric(end_df[c], errors="coerce")

    blocks_df = pd.merge(pre_df, post_df, on=["participant_id", "condition"], how="outer", suffixes=("_pre", "_post"))
    if "updated_at_pre" in blocks_df.columns or "updated_at_post" in blocks_df.columns:
        blocks_df["_t_pre"] = pd.to_datetime(blocks_df.get("updated_at_pre"), errors="coerce")
        blocks_df["_t_post"] = pd.to_datetime(blocks_df.get("updated_at_post"), errors="coerce")
        blocks_df["_t_any"] = blocks_df["_t_post"].fillna(blocks_df["_t_pre"])
        blocks_df["block_position"] = blocks_df.groupby("participant_id")["_t_any"].rank(method="first").astype("Int64")

    return participants_df, pre_df, post_df, end_df, blocks_df


def ensure_outdirs(outdir: str) -> Tuple[str, str]:
    tables_dir = os.path.join(outdir, "tables")
    figs_dir = os.path.join(outdir, "figures")
    os.makedirs(tables_dir, exist_ok=True)
    os.makedirs(figs_dir, exist_ok=True)
    return tables_dir, figs_dir


def save_figure(fig: plt.Figure, path_base: str, tif: bool) -> List[str]:
    paths = []
    eps_path = path_base + ".eps"
    fig.savefig(eps_path, format="eps", bbox_inches="tight")
    paths.append(eps_path)
    png_path = path_base + ".png"
    fig.savefig(png_path, format="png", dpi=300, bbox_inches="tight")
    paths.append(png_path)
    if tif:
        tif_path = path_base + ".tif"
        fig.savefig(tif_path, format="tiff", dpi=600, bbox_inches="tight")
        paths.append(tif_path)
    return paths


def save_table1(participants_df: pd.DataFrame, tables_dir: str) -> str:
    preferred_cols = [
        "participant_id",
        "session_type",
        "order",
        "age_range",
        "musical_experience",
        "theory_familiarity",
        "tonnetz_familiarity",
        "generative_experience",
        "color_deficiency",
        "light_sensitivity",
        "perceptual_comments",
    ]
    cols = [c for c in preferred_cols if c in participants_df.columns]
    table1 = participants_df[cols].copy() if cols else participants_df.copy()
    path = os.path.join(tables_dir, "Table1_participant_overview.csv")
    table1.to_csv(path, index=False)
    return path


def median_iqr(series: pd.Series) -> str:
    s = series.dropna()
    if s.empty:
        return ""
    med = s.median()
    q1 = s.quantile(0.25)
    q3 = s.quantile(0.75)
    return f"{med:.2f} [{q1:.2f}, {q3:.2f}]"


def save_table2_key_likerts(
    pre_df: pd.DataFrame,
    post_df: pd.DataFrame,
    tables_dir: str,
    key_pre: List[str],
    key_post: List[str],
) -> str:
    rows = []
    for cond in CONDITION_ORDER:
        r: Dict[str, Any] = {
            "Condition": cond,
            "Condition label": CONDITION_LABELS[cond],
            "n_pre": int(pre_df[pre_df["condition"] == cond]["participant_id"].nunique()) if not pre_df.empty else 0,
            "n_post": int(post_df[post_df["condition"] == cond]["participant_id"].nunique()) if not post_df.empty else 0,
        }
        for item in key_pre:
            if item in pre_df.columns:
                r[A_LABELS.get(item, item)] = median_iqr(pre_df.loc[pre_df["condition"] == cond, item])
        for item in key_post:
            if item in post_df.columns:
                r[B_LABELS.get(item, item)] = median_iqr(post_df.loc[post_df["condition"] == cond, item])
        rows.append(r)

    t2 = pd.DataFrame(rows)
    path = os.path.join(tables_dir, "Table2_key_likerts_summary.csv")
    t2.to_csv(path, index=False)
    return path


def _count_best_rank(end_df: pd.DataFrame) -> pd.Series:
    best = []
    for _, r in end_df.iterrows():
        winner = None
        for cond in CONDITION_ORDER:
            col = f"rank_{cond}"
            if col in end_df.columns and pd.notna(r.get(col)) and float(r[col]) == 1.0:
                winner = cond
                break
        if winner is not None:
            best.append(winner)
    return pd.Series(best).value_counts().reindex(CONDITION_ORDER, fill_value=0)


def _count_categorical(end_df: pd.DataFrame, col: str) -> pd.Series:
    if col not in end_df.columns:
        return pd.Series([0, 0, 0], index=CONDITION_ORDER)
    vals = end_df[col].astype(str)
    vals = vals[vals.isin(CONDITION_ORDER)]
    return vals.value_counts().reindex(CONDITION_ORDER, fill_value=0)


def make_fig1_outcomes(end_df: pd.DataFrame, figs_dir: str, tif: bool) -> List[str]:
    best_counts = _count_best_rank(end_df)
    inter_counts = _count_categorical(end_df, "most_intermedial")
    mismatch_counts = _count_categorical(end_df, "biggest_mismatch")

    df = pd.DataFrame({
        "Best overall (rank=1)": best_counts,
        "Most intermedial": inter_counts,
        "Biggest mismatch": mismatch_counts,
    })

    x = list(range(len(CONDITION_ORDER)))
    width = 0.25

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.bar([i - width for i in x], df["Best overall (rank=1)"], width=width, label="Best overall (rank=1)")
    ax.bar([i for i in x], df["Most intermedial"], width=width, label="Most intermedial")
    ax.bar([i + width for i in x], df["Biggest mismatch"], width=width, label="Biggest mismatch")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{c}\n{CONDITION_LABELS[c]}" for c in CONDITION_ORDER])
    ax.set_ylabel("Count (participants)")
    ax.set_title("End-of-session categorical outcomes by condition")
    ax.legend(frameon=False)
    fig.tight_layout()

    paths = save_figure(fig, os.path.join(figs_dir, "Fig1_outcomes_counts"), tif=tif)
    plt.close(fig)
    return paths


def paired_dotplot(df: pd.DataFrame, item: str, title: str, ylabel: str, figs_dir: str, stem: str, tif: bool) -> List[str]:
    if item not in df.columns:
        raise ValueError(f"Item '{item}' not found.")

    piv = df.pivot_table(index="participant_id", columns="condition", values=item, aggfunc="first")
    piv = piv.reindex(columns=CONDITION_ORDER)

    fig, ax = plt.subplots(figsize=(7.0, 4.0))

    x_positions = {c: i for i, c in enumerate(CONDITION_ORDER)}
    jitter = 0.04

    def stable_jitter(key: str) -> float:
        digest = hashlib.md5(key.encode("utf-8")).digest()
        return jitter if (digest[0] % 2 == 0) else -jitter

    for pid, row in piv.iterrows():
        xs, ys = [], []
        for c in CONDITION_ORDER:
            v = row.get(c)
            if pd.notna(v):
                xs.append(x_positions[c])
                ys.append(float(v))
        if len(xs) >= 2:
            ax.plot(xs, ys, linewidth=1.0, alpha=0.6)
        for c in CONDITION_ORDER:
            v = row.get(c)
            if pd.notna(v):
                ax.scatter(
                    x_positions[c] + stable_jitter(f"{pid}-{c}"),
                    float(v),
                    s=30,
                    alpha=0.9,
                )

    meds = [piv[c].median(skipna=True) for c in CONDITION_ORDER]
    ax.plot([x_positions[c] for c in CONDITION_ORDER], meds, linewidth=2.5)

    ax.set_xticks([x_positions[c] for c in CONDITION_ORDER])
    ax.set_xticklabels([f"{c}\n{CONDITION_LABELS[c]}" for c in CONDITION_ORDER])
    ax.set_ylim(1, 7)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()

    paths = save_figure(fig, os.path.join(figs_dir, stem), tif=tif)
    plt.close(fig)
    return paths


def compute_intermediality_index(post_df: pd.DataFrame) -> pd.Series:
    required = ["B_1", "B_2", "B_3", "B_4", "B_5", "B_6"]
    for c in required:
        if c not in post_df.columns:
            raise ValueError(f"Missing required column for intermediality index: {c}")

    df = post_df[required].copy()
    df["B_5_rev"] = 8 - df["B_5"]
    df["B_6_rev"] = 8 - df["B_6"]
    idx = df[["B_1", "B_2", "B_3", "B_4", "B_5_rev", "B_6_rev"]].mean(axis=1, skipna=False)
    return idx


def compute_mismatch_index(post_df: pd.DataFrame) -> pd.Series:
    required = ["B_7", "B_8"]
    for c in required:
        if c not in post_df.columns:
            raise ValueError(f"Missing required column for mismatch index: {c}")

    df = post_df[required].copy()
    df["B_7_rev"] = 8 - df["B_7"]
    idx = df[["B_7_rev", "B_8"]].mean(axis=1, skipna=False)
    return idx


def compute_agency_index(pre_df: pd.DataFrame) -> pd.Series:
    required = ["A_2", "A_3", "A_4", "A_6"]
    for c in required:
        if c not in pre_df.columns:
            raise ValueError(f"Missing required column for agency index: {c}")
    df = pre_df[required].copy()
    idx = df[["A_2", "A_3", "A_4"]].mean(axis=1, skipna=False) - df["A_6"]
    return idx


def make_reliance_fig(post_df: pd.DataFrame, figs_dir: str, tif: bool) -> List[str]:
    for c in ["B_11", "B_12"]:
        if c not in post_df.columns:
            raise ValueError(f"Missing {c} for reliance figure.")

    meds = []
    for cond in CONDITION_ORDER:
        sub = post_df[post_df["condition"] == cond]
        meds.append({
            "condition": cond,
            "visual_median": sub["B_11"].median(skipna=True),
            "theory_median": sub["B_12"].median(skipna=True),
        })
    df = pd.DataFrame(meds)

    x = list(range(len(CONDITION_ORDER)))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    ax.bar([i - width / 2 for i in x], df["visual_median"], width=width, label="B11 Visual cues (median)")
    ax.bar([i + width / 2 for i in x], df["theory_median"], width=width, label="B12 Theory cues (median)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{c}\n{CONDITION_LABELS[c]}" for c in CONDITION_ORDER])
    ax.set_ylim(1, 7)
    ax.set_ylabel("Median Likert rating (1-7)")
    ax.set_title("Decision cues by condition (post-reveal)")
    ax.legend(frameon=False)
    fig.tight_layout()

    paths = save_figure(fig, os.path.join(figs_dir, "Fig5_reliance_visual_vs_theory"), tif=tif)
    plt.close(fig)
    return paths


def normalise_param_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, float) and np.isnan(x):
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    if isinstance(x, str):
        s = x.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                arr = json.loads(s)
                if isinstance(arr, list):
                    return [str(i).strip() for i in arr if str(i).strip()]
            except Exception:
                pass
        if "," in s:
            return [p.strip() for p in s.split(",") if p.strip()]
        return [s]
    return [str(x).strip()]


def make_param_salience_fig(post_df: pd.DataFrame, figs_dir: str, tables_dir: str, tif: bool) -> List[str]:
    if "param_influence" not in post_df.columns:
        raise ValueError("param_influence not found in post_df.")

    tmp = post_df[["participant_id", "condition", "param_influence"]].copy()
    tmp["param_influence"] = tmp["param_influence"].apply(normalise_param_list)
    exploded = tmp.explode("param_influence")
    exploded = exploded[exploded["param_influence"].notna() & (exploded["param_influence"] != "")]
    if exploded.empty:
        raise ValueError("No param_influence values after exploding.")

    counts = exploded.groupby(["condition", "param_influence"]).size().reset_index(name="count")
    counts.to_csv(os.path.join(tables_dir, "Table_param_influence_counts.csv"), index=False)

    top_n = 12
    top_params = counts.groupby("param_influence")["count"].sum().sort_values(ascending=False).head(top_n).index.tolist()
    counts = counts[counts["param_influence"].isin(top_params)].copy()

    piv = counts.pivot_table(index="param_influence", columns="condition", values="count", fill_value=0)
    piv = piv.reindex(columns=CONDITION_ORDER, fill_value=0)
    piv = piv.loc[top_params]

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    bottoms = None
    x = list(range(len(piv.index)))

    for cond in CONDITION_ORDER:
        vals = piv[cond].values
        if bottoms is None:
            ax.bar(x, vals, label=f"{cond} {CONDITION_LABELS[cond]}")
            bottoms = vals.copy()
        else:
            ax.bar(x, vals, bottom=bottoms, label=f"{cond} {CONDITION_LABELS[cond]}")
            bottoms = bottoms + vals

    ax.set_xticks(x)
    ax.set_xticklabels(piv.index.tolist(), rotation=45, ha="right")
    ax.set_ylabel("Count (mentions)")
    ax.set_title("Self-reported influential parameters by condition (post-reveal)")
    ax.legend(frameon=False)
    fig.tight_layout()

    paths = save_figure(fig, os.path.join(figs_dir, "Fig6_param_influence_by_condition"), tif=tif)
    plt.close(fig)
    return paths


def save_qualitative_tables(
    participants_df: pd.DataFrame,
    end_df: pd.DataFrame,
    blocks_df: pd.DataFrame,
    tables_dir: str,
) -> List[str]:
    paths = []

    if not participants_df.empty:
        cols = [
            "participant_id",
            "age_range",
            "musical_experience",
            "theory_familiarity",
            "tonnetz_familiarity",
            "generative_experience",
            "perceptual_comments",
            "color_deficiency",
            "light_sensitivity",
        ]
        cols = [c for c in cols if c in participants_df.columns]
        if cols:
            path = os.path.join(tables_dir, "Qualitative_background.csv")
            participants_df[cols].to_csv(path, index=False)
            paths.append(path)

    if not end_df.empty:
        cols = [
            "participant_id",
            "most_intermedial",
            "biggest_mismatch",
            "one_change",
            "reflection",
            "session_notes_transcription",
        ]
        cols = [c for c in cols if c in end_df.columns]
        if cols:
            path = os.path.join(tables_dir, "Qualitative_end_notes.csv")
            end_df[cols].to_csv(path, index=False)
            paths.append(path)

    if not blocks_df.empty:
        cols = [
            "participant_id",
            "condition",
            "aim",
            "strategy",
            "expectation_vs_outcome",
            "interference_notes",
            "param_influence",
            "param_other",
        ]
        # Some columns may have suffixes after merge; handle both.
        col_map = {}
        for c in cols:
            if c in blocks_df.columns:
                col_map[c] = c
            elif f"{c}_pre" in blocks_df.columns:
                col_map[c] = f"{c}_pre"
            elif f"{c}_post" in blocks_df.columns:
                col_map[c] = f"{c}_post"
        if col_map:
            path = os.path.join(tables_dir, "Qualitative_block_notes.csv")
            out_cols = ["participant_id", "condition"] + [c for c in cols if c in col_map]
            blocks_df[[col_map.get(c, c) for c in out_cols]].rename(columns={v: k for k, v in col_map.items()}).to_csv(path, index=False)
            paths.append(path)

    return paths


def holm_correction(pvals: List[float]) -> List[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.zeros(m, dtype=float)
    for i, idx in enumerate(order):
        adj[idx] = min((m - i) * pvals[idx], 1.0)
    for i in range(m - 2, -1, -1):
        idx_i = order[i]
        idx_j = order[i + 1]
        adj[idx_i] = min(adj[idx_i], adj[idx_j])
    return adj.tolist()


def kendalls_w_from_friedman(chi2: float, n: int, k: int) -> Optional[float]:
    if n <= 0 or k <= 1:
        return None
    return float(chi2) / float(n * (k - 1))


def friedman_item(df: pd.DataFrame, item: str) -> Dict[str, Any]:
    out = {"item": item, "test": "friedman", "n": 0, "chi2": None, "p": None, "kendalls_w": None}
    if friedmanchisquare is None:
        out["note"] = "scipy not available"
        return out
    wide = df.pivot_table(index="participant_id", columns="condition", values=item, aggfunc="first")
    if not set(CONDITION_ORDER).issubset(wide.columns):
        out["note"] = "missing conditions in data"
        return out
    wide = wide[CONDITION_ORDER].dropna()
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
    if not set(CONDITION_ORDER).issubset(wide.columns):
        return pd.DataFrame([{"item": item, "note": "missing conditions in data"}])

    pairs = [("A", "B"), ("A", "C"), ("B", "C")]
    rows = []
    pvals = []

    for x, y in pairs:
        w = wide[[x, y]].dropna()
        if w.shape[0] < 3:
            rows.append({"item": item, "pair": f"{x}-{y}", "n": int(w.shape[0]), "stat": None, "p": None})
            pvals.append(np.nan)
            continue
        res = wilcoxon(w[x], w[y], zero_method="wilcox", correction=False, alternative="two-sided", mode="auto")
        rows.append({"item": item, "pair": f"{x}-{y}", "n": int(w.shape[0]), "stat": float(res.statistic), "p": float(res.pvalue)})
        pvals.append(float(res.pvalue))

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
    for c in CONDITION_ORDER:
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


def save_stats_tables(blocks_df: pd.DataFrame, tables_dir: str) -> List[str]:
    paths = []
    items = [f"A_{i}" for i in range(1, 8)] + [f"B_{i}" for i in range(1, 13)]

    stats_rows = []
    pairwise_rows = []
    desc_rows = []

    for item in items:
        if item not in blocks_df.columns:
            continue
        stats_rows.append(friedman_item(blocks_df, item))
        pairwise_rows.append(wilcoxon_pairs(blocks_df, item))
        desc_rows.append(describe_by_condition(blocks_df, item))

    if stats_rows:
        df_stats = pd.DataFrame(stats_rows)
        path = os.path.join(tables_dir, "Table_friedman_tests.csv")
        df_stats.to_csv(path, index=False)
        paths.append(path)
    if pairwise_rows:
        df_pairwise = pd.concat(pairwise_rows, ignore_index=True)
        path = os.path.join(tables_dir, "Table_wilcoxon_pairwise.csv")
        df_pairwise.to_csv(path, index=False)
        paths.append(path)
    if desc_rows:
        df_desc = pd.concat(desc_rows, ignore_index=True)
        path = os.path.join(tables_dir, "Table_likert_descriptives.csv")
        df_desc.to_csv(path, index=False)
        paths.append(path)

    return paths


def make_order_check_fig(blocks_df: pd.DataFrame, figs_dir: str, tif: bool) -> List[str]:
    if "block_position" not in blocks_df.columns or "A_4" not in blocks_df.columns:
        raise ValueError("block_position or A_4 not available for order check.")
    df = blocks_df[blocks_df["block_position"].notna()].copy()
    if df.empty:
        raise ValueError("No block_position values for order check.")

    groups = sorted(df["block_position"].dropna().unique().tolist())
    data = [df.loc[df["block_position"] == g, "A_4"].dropna().values for g in groups]
    if not any(len(d) for d in data):
        raise ValueError("No A_4 values for order check.")

    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.boxplot(data, widths=0.5, patch_artist=False, showfliers=False)
    ax.set_xticks(range(1, len(groups) + 1))
    ax.set_xticklabels([str(g) for g in groups])
    ax.set_title("A_4 by block position (learning check)")
    ax.set_ylabel("Likert rating (1-7)")
    ax.grid(axis="y", linestyle=":", linewidth=0.6)
    fig.tight_layout()

    paths = save_figure(fig, os.path.join(figs_dir, "Fig8_A4_by_block_position"), tif=tif)
    plt.close(fig)
    return paths


def main() -> int:
    ap = argparse.ArgumentParser()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_input = None
    for name in ["data.json", "sections_plus_transcriptions.json", "sections.json"]:
        candidate = os.path.join(base_dir, name)
        if os.path.exists(candidate):
            default_input = candidate
            break

    ap.add_argument("--input", default=default_input, help="Path to merged JSON results file.")
    ap.add_argument("--outdir", default=os.path.join(base_dir, "outputs"),
                    help="Output directory (creates tables/ and figures/).")
    ap.add_argument("--no-tif", dest="tif", action="store_false",
                    help="Disable .tif (600 dpi) export.")
    ap.add_argument("--no-table2", dest="make_table2", action="store_false",
                    help="Skip Table2 key Likert summary (median [IQR]).")
    ap.add_argument("--no-overload", dest="make_overload", action="store_false",
                    help="Skip overload paired plot (B6).")
    ap.add_argument("--no-reliance", dest="make_reliance", action="store_false",
                    help="Skip reliance figure (B11 vs B12).")
    ap.add_argument("--no-param-salience", dest="make_param_salience", action="store_false",
                    help="Skip param influence salience plot.")

    ap.add_argument("--make-mismatch", action="store_true", help="Generate optional mismatch index paired plot (B7/B8).")
    ap.add_argument("--make-stats", action="store_true", help="Generate Friedman/Wilcoxon tables for A_1..A_7 and B_1..B_12.")
    ap.add_argument("--make-agency", action="store_true", help="Generate paired plot for agency index (A2-A4 minus A6).")
    ap.add_argument("--make-order-check", action="store_true", help="Generate A_4 by block position plot.")

    ap.set_defaults(tif=True, make_table2=True, make_overload=True, make_reliance=True, make_param_salience=True)
    args = ap.parse_args()
    if not args.input:
        ap.error("No input JSON found. Provide --input PATH.")

    log_lines: List[str] = []

    records = load_records(args.input, log_lines)
    participants_df, pre_df, post_df, end_df, blocks_df = build_tables(records)
    tables_dir, figs_dir = ensure_outdirs(args.outdir)

    log_lines.append(f"participants: {participants_df['participant_id'].nunique() if not participants_df.empty else 0}")
    log_lines.append(f"pre blocks: {len(pre_df)}")
    log_lines.append(f"post blocks: {len(post_df)}")

    # ---- Table 1 (mandatory)
    t1 = save_table1(participants_df, tables_dir)
    print(f"Wrote: {t1}")

    # ---- Figure 1 (mandatory)
    for p in make_fig1_outcomes(end_df, figs_dir, tif=args.tif):
        print(f"Wrote: {p}")

    # ---- Figure 2 (mandatory): A3 control/steering
    if pre_df.empty:
        print("WARNING: pre_df empty; cannot generate Fig2 (A3).")
    else:
        for p in paired_dotplot(
            df=pre_df,
            item="A_3",
            title="Within-participant control/steering across conditions (A3)",
            ylabel="Likert rating (1-7)",
            figs_dir=figs_dir,
            stem="Fig2_paired_control_A3",
            tif=args.tif,
        ):
            print(f"Wrote: {p}")

    # ---- Figure 3 (mandatory): Intermediality Index (B1-B6 with reversals)
    if post_df.empty:
        print("WARNING: post_df empty; cannot generate Fig3 (Intermediality Index).")
    else:
        post_df = post_df.copy()
        post_df["IntermedialityIndex"] = compute_intermediality_index(post_df)
        for p in paired_dotplot(
            df=post_df,
            item="IntermedialityIndex",
            title="Within-participant Intermediality Index across conditions (B1-B6, reversals applied)",
            ylabel="Index (mean of items; 1-7 scale)",
            figs_dir=figs_dir,
            stem="Fig3_paired_intermediality_index",
            tif=args.tif,
        ):
            print(f"Wrote: {p}")

    # ---- Optional: Table 2 key Likerts
    if args.make_table2:
        key_pre = ["A_1", "A_3", "A_5", "A_6"]
        key_post = ["B_1", "B_2", "B_6", "B_7", "B_10"]
        t2 = save_table2_key_likerts(pre_df, post_df, tables_dir, key_pre=key_pre, key_post=key_post)
        print(f"Wrote: {t2}")

    # ---- Optional: overload (B6)
    if args.make_overload and not post_df.empty and "B_6" in post_df.columns:
        for p in paired_dotplot(
            df=post_df,
            item="B_6",
            title="Within-participant perceptual overload across conditions (B6)",
            ylabel="Likert rating (1-7)",
            figs_dir=figs_dir,
            stem="Fig4_paired_overload_B6",
            tif=args.tif,
        ):
            print(f"Wrote: {p}")

    # ---- Optional: mismatch index (B7/B8)
    if args.make_mismatch and not post_df.empty:
        post_df = post_df.copy()
        post_df["MismatchIndex"] = compute_mismatch_index(post_df)
        for p in paired_dotplot(
            df=post_df,
            item="MismatchIndex",
            title="Within-participant mismatch index across conditions (B7/B8)",
            ylabel="Index (mean of items; 1-7 scale)",
            figs_dir=figs_dir,
            stem="Fig4b_paired_mismatch_index",
            tif=args.tif,
        ):
            print(f"Wrote: {p}")

    # ---- Optional: reliance (B11 vs B12)
    if args.make_reliance and not post_df.empty:
        for p in make_reliance_fig(post_df, figs_dir, tif=args.tif):
            print(f"Wrote: {p}")

    # ---- Optional: param salience
    if args.make_param_salience and not post_df.empty:
        for p in make_param_salience_fig(post_df, figs_dir, tables_dir, tif=args.tif):
            print(f"Wrote: {p}")

    # ---- Optional: agency index
    if args.make_agency and not pre_df.empty:
        pre_df = pre_df.copy()
        pre_df["AgencyIndex"] = compute_agency_index(pre_df)
        for p in paired_dotplot(
            df=pre_df,
            item="AgencyIndex",
            title="Within-participant agency index across conditions (A2-A4 minus A6)",
            ylabel="Index (mean of items; 1-7 scale)",
            figs_dir=figs_dir,
            stem="Fig7_paired_agency_index",
            tif=args.tif,
        ):
            print(f"Wrote: {p}")

    # ---- Optional: order/learning check
    if args.make_order_check and not blocks_df.empty:
        try:
            for p in make_order_check_fig(blocks_df, figs_dir, tif=args.tif):
                print(f"Wrote: {p}")
        except Exception as exc:
            print(f"WARNING: order check skipped ({exc})")

    # ---- Optional: stats tables
    if args.make_stats and not blocks_df.empty:
        for p in save_stats_tables(blocks_df, tables_dir):
            print(f"Wrote: {p}")

    # ---- Qualitative extracts + audit (always)
    for p in save_qualitative_tables(participants_df, end_df, blocks_df, tables_dir):
        print(f"Wrote: {p}")

    if not pre_df.empty:
        path = os.path.join(tables_dir, "Audit_pre_block_items.csv")
        pre_df.to_csv(path, index=False)
        print(f"Wrote: {path}")
    if not post_df.empty:
        path = os.path.join(tables_dir, "Audit_post_block_items.csv")
        post_df.to_csv(path, index=False)
        print(f"Wrote: {path}")
    if not blocks_df.empty:
        path = os.path.join(tables_dir, "Audit_blocks_merged.csv")
        blocks_df.to_csv(path, index=False)
        print(f"Wrote: {path}")

    # ---- Summary + log
    summary = {
        "N_participants": int(participants_df["participant_id"].nunique()) if not participants_df.empty else 0,
        "N_blocks_total": int(blocks_df[blocks_df["condition"].isin(CONDITION_ORDER)].shape[0]) if not blocks_df.empty else 0,
        "N_blocks_expected": int(participants_df["participant_id"].nunique()) * 3 if not participants_df.empty else 0,
        "missing_pct": None,
    }
    likert_cols = [c for c in blocks_df.columns if c.startswith("A_") or c.startswith("B_")]
    if likert_cols:
        miss = blocks_df[likert_cols].isna().mean().mean()
        summary["missing_pct"] = None if miss != miss else float(miss * 100.0)

    pref_counts = _count_best_rank(end_df)
    summary.update({
        "pref_A_n": int(pref_counts.get("A", 0)),
        "pref_B_n": int(pref_counts.get("B", 0)),
        "pref_C_n": int(pref_counts.get("C", 0)),
    })
    inter_counts = _count_categorical(end_df, "most_intermedial")
    summary.update({
        "most_intermedial_A_n": int(inter_counts.get("A", 0)),
        "most_intermedial_B_n": int(inter_counts.get("B", 0)),
        "most_intermedial_C_n": int(inter_counts.get("C", 0)),
    })
    mismatch_counts = _count_categorical(end_df, "biggest_mismatch")
    summary.update({
        "biggest_mismatch_A_n": int(mismatch_counts.get("A", 0)),
        "biggest_mismatch_B_n": int(mismatch_counts.get("B", 0)),
        "biggest_mismatch_C_n": int(mismatch_counts.get("C", 0)),
    })

    summary_path = os.path.join(args.outdir, "summary_numbers.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote: {summary_path}")

    log_path = os.path.join(args.outdir, "log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        for line in log_lines:
            f.write(line + "\n")
    print(f"Wrote: {log_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
