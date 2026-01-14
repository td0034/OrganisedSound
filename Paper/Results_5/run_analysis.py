#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from config import CONDITION_LABELS, CONDITION_ORDER, ITEMS
from export import save_figure
from io_ingest import load_records
from plots_estimation import plot_estimation
from plots_likert import plot_likert_panel
from plots_outcomes import plot_end_outcomes
from plots_params import plot_param_bars, plot_param_heatmap, plot_param_stacked
from tables import (
    make_item_descriptives,
    make_param_counts_table,
    make_table1,
    make_table2,
    make_table3,
)
from transform import (
    build_blocks_long,
    build_blocks_wide,
    build_end_df,
    build_missingness_report,
    build_order_map,
    build_param_counts,
    build_participants_df,
    find_unknown_params,
    to_numeric,
)


def compute_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit_hash(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.decode("utf-8").strip()
    except Exception:
        return ""


def detect_non_numeric(records: List[Dict[str, Any]]) -> List[str]:
    warnings: List[str] = []
    for rec in records:
        section = rec.get("section_key") or ""
        if section.endswith("_pre"):
            items = [k for k, v in ITEMS.items() if v.get("phase") == "pre"]
        elif section.endswith("_post"):
            items = [k for k, v in ITEMS.items() if v.get("phase") == "post"]
        else:
            continue
        payload = rec.get("payload") or {}
        for item in items:
            raw = payload.get(item)
            if raw is None:
                continue
            if to_numeric(raw) is None:
                warnings.append(f"Non-numeric Likert entry: {rec.get('participant_id')} {section} {item}={raw}")
    return warnings


def detect_order_issues(participants_df: pd.DataFrame) -> List[str]:
    warnings: List[str] = []
    if participants_df.empty or "order" not in participants_df.columns:
        return warnings
    for _, row in participants_df.iterrows():
        order = row.get("order")
        if not order:
            continue
        letters = [c for c in str(order) if c in CONDITION_ORDER]
        if len(letters) != 3:
            warnings.append(f"Unexpected order value for {row.get('participant_id')}: {order}")
    return warnings


def load_manifest(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return json.loads(path.read_text())


def write_captions(outdir: Path, manifest: List[Dict[str, Any]]) -> None:
    captions_dir = outdir / "captions"
    captions_dir.mkdir(parents=True, exist_ok=True)
    for path in captions_dir.glob("*.txt"):
        path.unlink()

    fig_captions = {
        "Fig1_outcomes": (
            "Counts of best overall rank (1), most intermedial selection, and biggest mismatch by block condition "
            f"(A={CONDITION_LABELS['A']}, B={CONDITION_LABELS['B']}, C={CONDITION_LABELS['C']})."
        ),
        "Fig2_partA_likert": (
            "Diverging stacked Likert responses for Part A (pre-reveal) items by block condition. "
            "Bars show within-condition percentages centered on neutral (4)."
        ),
        "Fig3_partB_likert": (
            "Diverging stacked Likert responses for Part B (post-reveal) items by block condition. "
            "Bars show within-condition percentages centered on neutral (4)."
        ),
        "Fig4_estimation_contrasts": (
            "Paired difference estimation plots for key contrasts (C-A, C-B, B-A). Points show individual "
            "within-participant differences; black markers indicate mean with bootstrap 95% CI (percentiles "
            "from resampled participants)."
        ),
        "Fig5_param_heatmap": (
            "Heatmap of parameter influence nominations by condition. Cells show counts of nominations per "
            f"parameter (A={CONDITION_LABELS['A']}, B={CONDITION_LABELS['B']}, C={CONDITION_LABELS['C']})."
        ),
        "Fig6_param_influence_stacked": (
            "Stacked bar chart of parameter influence nominations by condition; colors match Fig1 for "
            f"A={CONDITION_LABELS['A']}, B={CONDITION_LABELS['B']}, C={CONDITION_LABELS['C']}."
        ),
    }

    for entry in manifest:
        base = entry.get("output_basename")
        if base in fig_captions:
            (captions_dir / f"{base}.txt").write_text(fig_captions[base])

    table_captions = {
        "Table1_participant_overview": (
            "Participant overview with anonymized IDs (1-9), background measures, and block order. "
            "Order indicates the within-participant condition sequence."
        ),
        "Table2a_likert_subset": (
            "Median [Q1, Q3] Likert ratings (1-7) for key items by condition; N is the count of participants. "
            "Values in square brackets are the interquartile range (Q1, Q3)."
        ),
        "Table2b_likert_full": (
            "Median [Q1, Q3] Likert ratings (1-7) for all A1-A7 and B1-B12 items by condition; N is the count "
            "of participants. Values in square brackets are the interquartile range (Q1, Q3)."
        ),
        "Table3_construct_mapping": (
            "Construct mapping for composite indices, including item lists, reverse-coded items, formulas, and "
            "interpretation guidance."
        ),
        "Audit_blocks_long": "Audit table: long-format item-level responses by participant, condition, and phase.",
        "Audit_blocks_wide": "Audit table: wide-format block-level responses with items and composite indices.",
        "Audit_missingness_report": "Audit table: per-participant missingness summary by item and phase.",
        "Audit_item_descriptives": "Audit table: descriptive statistics by item and condition.",
        "Audit_param_influence_counts": "Audit table: parameter influence nomination counts by condition.",
        "Qualitative_background": "Qualitative background responses by participant.",
        "Qualitative_block_notes": "Qualitative block-level notes by participant and condition.",
        "Qualitative_end_notes": "Qualitative end-of-session notes by participant.",
    }

    tables_dir = outdir / "tables"
    for stem, caption in table_captions.items():
        if (tables_dir / f"{stem}.csv").exists():
            (captions_dir / f"{stem}.txt").write_text(caption)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run TZ5 Organised Sound analysis pipeline.")
    ap.add_argument("--input", default="sections_plus_transcriptions.json", help="Input JSON file.")
    ap.add_argument("--outdir", default="outputs", help="Output directory.")
    ap.add_argument("--manifest", default="figures_manifest.json", help="Figure manifest JSON.")
    ap.add_argument("--paper-mode", action="store_true", help="Run full paper output set.")
    ap.add_argument("--no-tif", dest="make_tif", action="store_false", help="Skip TIFF exports.")
    ap.set_defaults(make_tif=True)
    args = ap.parse_args()

    base_dir = Path(__file__).resolve().parent
    input_path = (base_dir / args.input).resolve()
    outdir = (base_dir / args.outdir).resolve()
    figs_dir = outdir / "figures"
    tables_dir = outdir / "tables"
    figs_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(str(input_path))
    participants_df = build_participants_df(records)
    order_map = build_order_map(participants_df)
    end_df = build_end_df(records)
    long_df = build_blocks_long(records, order_map)
    wide_df = build_blocks_wide(records, order_map)

    param_counts = build_param_counts(wide_df)

    # --- audit outputs
    long_path = tables_dir / "Audit_blocks_long.csv"
    wide_path = tables_dir / "Audit_blocks_wide.csv"
    missing_path = tables_dir / "Audit_missingness_report.csv"
    long_df.to_csv(long_path, index=False)
    wide_df.to_csv(wide_path, index=False)
    missing_df = build_missingness_report(long_df)
    missing_df.to_csv(missing_path, index=False)

    # --- tables
    make_table1(participants_df, str(tables_dir))
    make_table2(long_df, str(tables_dir))
    make_table3(str(tables_dir))
    make_item_descriptives(long_df, str(tables_dir))
    make_param_counts_table(param_counts, str(tables_dir))

    # --- figures from manifest
    manifest_path = (base_dir / args.manifest).resolve()
    manifest = load_manifest(manifest_path)

    xmax = None
    if not param_counts.empty:
        xmax = float(param_counts["count"].max()) + 0.5

    for entry in manifest:
        plot_type = entry.get("plot_type")
        size = entry.get("size", "double")
        out_base = figs_dir / entry.get("output_basename")
        title = entry.get("title")
        if plot_type == "outcomes":
            fig = plot_end_outcomes(end_df, title=title)
        elif plot_type == "likert_panel":
            items = entry.get("items", [])
            fig = plot_likert_panel(long_df, items, title=title)
        elif plot_type == "estimation":
            measures = entry.get("measures", [])
            fig = plot_estimation(wide_df, measures)
        elif plot_type == "param_heatmap":
            fig = plot_param_heatmap(param_counts, title=title)
        elif plot_type == "param_stacked":
            fig = plot_param_stacked(param_counts, title=title)
        elif plot_type == "param_bars":
            condition = entry.get("condition")
            fig = plot_param_bars(param_counts, condition, title=title, xmax=xmax)
        else:
            raise ValueError(f"Unknown plot_type: {plot_type}")
        size_scale = (1.0, 1.0)
        bbox_inches = "tight"
        if plot_type == "likert_panel":
            size = None
            bbox_inches = None
        save_figure(
            fig,
            str(out_base),
            size_key=size,
            make_tif=args.make_tif,
            size_scale=size_scale,
            bbox_inches=bbox_inches,
        )

    write_captions(outdir, manifest)

    # --- logging
    warnings: List[str] = []
    warnings.extend(detect_non_numeric(records))
    warnings.extend(detect_order_issues(participants_df))
    unknown_params = find_unknown_params(param_counts)
    for param in unknown_params:
        warnings.append(f"Unknown parameter name: {param}")

    participant_count = participants_df["participant_id"].nunique() if not participants_df.empty else 0
    expected_blocks = participant_count * 3
    actual_blocks = wide_df[["participant_id", "condition"]].dropna().drop_duplicates().shape[0]
    if expected_blocks != actual_blocks:
        warnings.append(f"Expected {expected_blocks} blocks, found {actual_blocks}.")

    missing_total = 0
    if not missing_df.empty and "item" in missing_df.columns:
        missing_total = missing_df[missing_df["item"] == "__TOTAL__"]["n_missing"].sum()
    if missing_total:
        warnings.append(f"Missingness detected: {int(missing_total)} missing values.")

    log_lines = [
        f"Run timestamp: {datetime.now(timezone.utc).isoformat()}",
        f"Input: {input_path}",
        f"Records: {len(records)}",
        f"Participants: {participants_df['participant_id'].nunique() if not participants_df.empty else 0}",
        f"Blocks (wide rows): {actual_blocks}",
        f"Input hash: {compute_file_hash(input_path)}",
    ]
    git_hash = git_commit_hash(base_dir.parents[2])
    if git_hash:
        log_lines.append(f"Git commit: {git_hash}")
    if warnings:
        log_lines.append("Warnings:")
        log_lines.extend([f"- {w}" for w in warnings])

    (outdir / "log.txt").write_text("\n".join(log_lines))

    summary = {
        "participants": participants_df["participant_id"].nunique() if not participants_df.empty else 0,
        "blocks": actual_blocks,
        "input_hash": compute_file_hash(input_path),
        "git_commit": git_hash,
    }
    (outdir / "summary_numbers.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
