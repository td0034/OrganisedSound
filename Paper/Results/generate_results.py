#!/usr/bin/env python3
"""
generate_results.py
Generate tables and plots for the Organised Sound results section.

Outputs are written under Paper/Results/output/<section>/[tables|figures|captions].
Captions are created once and not overwritten unless --overwrite-captions is set.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

try:
    from wordcloud import WordCloud, STOPWORDS
    WORDCLOUD_AVAILABLE = True
except Exception:
    WORDCLOUD_AVAILABLE = False


sns.set_theme(style="whitegrid")


BLOCK_TO_COND = {"A": "V", "B": "A", "C": "AV"}
COND_LABELS = {"V": "Visual-only", "A": "Audio-only", "AV": "Audiovisual", "DYAD": "Dyad"}
COND_ORDER = ["V", "A", "AV"]

PRE_ITEMS = {
    "A_1": "satisfaction",
    "A_2": "intention_clarity",
    "A_3": "steerability",
    "A_4": "interface_understanding",
    "A_5": "useful_surprise",
    "A_6": "frustrating_unpredictability",
    "A_7": "anticipated_interest",
}

POST_ITEMS = {
    "B_1": "fusion_process",
    "B_2": "media_balance",
    "B_3": "coherence",
    "B_4": "constructive_interference",
    "B_5": "destructive_interference",
    "B_6": "overload",
    "B_7": "expectation_match",
    "B_8": "interpretation_change",
    "B_9": "causal_story",
    "B_10": "system_autonomy",
    "B_11": "visual_reliance",
    "B_12": "theory_reliance",
}

PRE_QUESTIONS = {
    "A_1": "I am satisfied with the outcome I achieved for this block’s task.",
    "A_2": "I had a clear intention for what I was trying to achieve.",
    "A_3": "I felt able to steer the system toward my intention.",
    "A_4": "The parameter interface felt understandable and workable.",
    "A_5": "The system surprised me in useful/interesting ways.",
    "A_6": "The system behaved unpredictably in a frustrating way.",
    "A_7": "I would be confident that others would find this result interesting.",
}

POST_QUESTIONS = {
    "B_1": "The revealed audio and light felt like two views of the same underlying process.",
    "B_2": "Sound and light felt balanced (neither dominated as the ‘real’ carrier of form).",
    "B_3": "The relationship between sound and light felt coherent/legible.",
    "B_4": "Sound and light reinforced each other (constructive interference).",
    "B_5": "Sound and light competed or contradicted each other (destructive interference).",
    "B_6": "The combined result felt overwhelming (perceptual overload).",
    "B_7": "The revealed modality matched what I expected.",
    "B_8": "The revealed modality changed my interpretation of what I had made.",
    "B_9": "I can describe a plausible causal story of how the system produced the result.",
    "B_10": "I felt that the system had strong autonomy (it ‘wanted’ to do its own thing).",
    "B_11": "I relied on visual pattern cues to make decisions in this block.",
    "B_12": "I relied on Tonnetz/music-theory expectations to make decisions in this block.",
}

RATER_MAP = {
    "R_1": "preference",
    "R_2": "coherence",
    "R_3": "novelty",
    "R_4": "fusion",
    "R_5": "constructive",
    "R_6": "destructive",
    "R_7": "overload",
    "R_8": "inferred_structure",
    "R_9": "perceived_agency",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    root = repo_root()
    p = argparse.ArgumentParser(description="Generate results tables and plots.")
    p.add_argument(
        "--sections-json",
        default=root / "Paper" / "Results" / "input" / "sections_edited.json",
        type=Path,
    )
    p.add_argument(
        "--addendum-json",
        default=root / "Paper" / "Results" / "input" / "participant_addendum_edited.json",
        type=Path,
    )
    p.add_argument(
        "--rater-csv",
        default=root / "Rater Survey/exports/ratings.csv",
        type=Path,
    )
    p.add_argument(
        "--manifest-csv",
        default=root / "Rater Survey/clips/manifest.csv",
        type=Path,
    )
    p.add_argument(
        "--out-root",
        default=root / "Paper" / "Results" / "output",
        type=Path,
    )
    p.add_argument(
        "--overwrite-captions",
        action="store_true",
        help="Overwrite existing caption files.",
    )
    return p.parse_args()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_caption(path: Path, text: str, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        return
    path.write_text(text.strip() + "\n", encoding="utf-8")


def read_sections_json(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df["updated_at"] = pd.to_datetime(df.get("updated_at"), errors="coerce")
    payload = df["payload"].apply(lambda v: v or {})
    payload_df = pd.json_normalize(payload)
    # Avoid column name collisions (e.g., payload participant_id inside meta).
    dup_cols = [c for c in payload_df.columns if c in df.columns]
    if dup_cols:
        payload_df = payload_df.drop(columns=dup_cols)
    df = pd.concat([df.drop(columns=["payload"]), payload_df], axis=1)
    return df


def latest_by_section(df: pd.DataFrame, section_key: str) -> pd.DataFrame:
    sub = df[df["section_key"] == section_key].copy()
    if sub.empty:
        return sub
    sub = sub.sort_values("updated_at")
    sub = sub.groupby("participant_id", as_index=False).tail(1)
    return sub


def merge_background_fields(left: pd.DataFrame, background: pd.DataFrame, fields: List[str]) -> pd.DataFrame:
    if background.empty:
        return left.copy()
    fields = [f for f in fields if f in background.columns]
    if not fields:
        return left.copy()
    bg = background[["participant_id"] + fields].copy()
    left2 = left.copy()
    drop_cols = [f for f in fields if f in left2.columns]
    if drop_cols:
        left2 = left2.drop(columns=drop_cols)
    return left2.merge(bg, on="participant_id", how="left")


def parse_order(order_raw: Optional[str]) -> List[str]:
    if not order_raw:
        return []
    order = str(order_raw).strip()
    order = order.replace("→", "->")
    order = order.replace(" ", "")
    parts = [p for p in order.split("->") if p]
    return parts


def add_block_position(meta_df: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    order_map: Dict[str, Dict[str, int]] = {}
    for _, row in meta_df.iterrows():
        pid = row.get("participant_id")
        order = parse_order(row.get("order"))
        pos = {b: idx + 1 for idx, b in enumerate(order)}
        if pid:
            order_map[pid] = pos
    df = df.copy()
    df["block_position"] = df.apply(
        lambda r: order_map.get(r["participant_id"], {}).get(r["block"]), axis=1
    )
    return df


def extract_block(df: pd.DataFrame, block: str, part: str) -> pd.DataFrame:
    key = f"block_{block}_{part}"
    sub = latest_by_section(df, key)
    if sub.empty:
        return sub
    sub = sub.copy()
    sub["block"] = block
    sub["condition"] = BLOCK_TO_COND.get(block)
    return sub


def as_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def make_long(df: pd.DataFrame, items: Dict[str, str]) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        for key, label in items.items():
            score = row.get(key)
            if score is None or score == "":
                continue
            rows.append(
                {
                    "participant_id": row.get("participant_id"),
                    "block": row.get("block"),
                    "condition": row.get("condition"),
                    "item_key": key,
                    "item": label,
                    "score": score,
                    "preset_id": row.get("preset_id"),
                }
            )
    out = pd.DataFrame(rows)
    if not out.empty:
        out["score"] = as_numeric(out["score"])
    return out


def iqr(series: pd.Series) -> Tuple[float, float]:
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    return q1, q3


def summarize_by_condition(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    rows = []
    for cond in COND_ORDER:
        sub = df[df["condition"] == cond]
        scores = sub[value_col].dropna()
        if scores.empty:
            continue
        q1, q3 = iqr(scores)
        rows.append(
            {
                "condition": cond,
                "n": len(scores),
                "median": float(scores.median()),
                "mean": float(scores.mean()),
                "std": float(scores.std(ddof=1)) if len(scores) > 1 else 0.0,
                "iqr_low": float(q1),
                "iqr_high": float(q3),
            }
        )
    return pd.DataFrame(rows)


def box_with_points(ax, data: pd.DataFrame, y: str, title: str):
    sns.boxplot(ax=ax, data=data, x="condition", y=y, order=COND_ORDER, showfliers=False)
    sns.stripplot(
        ax=ax,
        data=data,
        x="condition",
        y=y,
        order=COND_ORDER,
        color="black",
        size=3,
        jitter=0.2,
        alpha=0.6,
    )
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_ylim(1, 7)
    ax.set_xticks(range(len(COND_ORDER)))
    ax.set_xticklabels([COND_LABELS.get(c, c) for c in COND_ORDER], rotation=0)


def save_figure(fig: plt.Figure, path_base: Path):
    fig.tight_layout()
    fig.savefig(path_base.with_suffix(".png"), dpi=200)
    fig.savefig(path_base.with_suffix(".eps"))
    plt.close(fig)


def parse_payload_json(value: str) -> dict:
    if value is None or value == "":
        return {}
    try:
        return json.loads(value)
    except Exception:
        try:
            return ast.literal_eval(value)
        except Exception:
            return {}


def cronbach_alpha(df: pd.DataFrame) -> Optional[float]:
    # df is items x observations (wide)
    if df.shape[1] < 2:
        return None
    df = df.dropna()
    if df.empty:
        return None
    item_vars = df.var(axis=0, ddof=1)
    total_var = df.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return None
    n_items = df.shape[1]
    alpha = (n_items / (n_items - 1)) * (1 - item_vars.sum() / total_var)
    return float(alpha)


def build_outputs(args: argparse.Namespace) -> None:
    out_root = ensure_dir(Path(args.out_root))

    # Sections (participant)
    sections_df = read_sections_json(args.sections_json)
    if sections_df.empty:
        raise SystemExit("No section data found.")

    background = latest_by_section(sections_df, "background")
    meta = latest_by_section(sections_df, "meta")
    end = latest_by_section(sections_df, "end")
    dyad = latest_by_section(sections_df, "dyad")
    dyad_gate = latest_by_section(sections_df, "dyad_gate")

    # Blocks
    blocks_pre = pd.concat(
        [extract_block(sections_df, b, "pre") for b in ["A", "B", "C"]],
        ignore_index=True,
    )
    blocks_post = pd.concat(
        [extract_block(sections_df, b, "post") for b in ["A", "B", "C"]],
        ignore_index=True,
    )

    blocks_pre = add_block_position(meta, blocks_pre)
    blocks_post = add_block_position(meta, blocks_post)

    pre_long = make_long(blocks_pre, PRE_ITEMS)
    post_long = make_long(blocks_post, POST_ITEMS)

    # 4.1 Dataset tables
    sec_4_1 = ensure_dir(out_root / "4_1_dataset")
    tdir = ensure_dir(sec_4_1 / "tables")
    cdir = ensure_dir(sec_4_1 / "captions")

    participants = meta.copy()
    participants = merge_background_fields(
        participants,
        background,
        [
            "age_range",
            "musical_experience",
            "theory_familiarity",
            "generative_experience",
            "tonnetz_familiarity",
            "color_deficiency",
            "light_sensitivity",
        ],
    )
    if "dyad_done" in dyad_gate.columns:
        participants = participants.merge(dyad_gate[["participant_id", "dyad_done"]], on="participant_id", how="left")
    if "dyad_id" in dyad.columns:
        participants = participants.merge(dyad[["participant_id", "dyad_id"]], on="participant_id", how="left")
    if "dyad_done" in participants.columns:
        participants["dyad_participation"] = participants["dyad_done"].fillna("No")
    else:
        participants["dyad_participation"] = "No"
    participants_out = participants.reindex(columns=[
        "participant_id",
        "order",
        "session_type",
        "musical_experience",
        "theory_familiarity",
        "generative_experience",
        "tonnetz_familiarity",
        "age_range",
        "color_deficiency",
        "light_sensitivity",
        "dyad_participation",
        "dyad_id",
    ]).copy()
    participants_out.to_csv(tdir / "Table1_participants.csv", index=False)
    write_caption(
        cdir / "Table1_participants.txt",
        "Participant summary (background and session metadata).",
        args.overwrite_captions,
    )

    order_counts = meta["order"].value_counts(dropna=False).rename_axis("order").reset_index(name="count")
    order_counts.to_csv(tdir / "Table1a_order_distribution.csv", index=False)
    write_caption(
        cdir / "Table1a_order_distribution.txt",
        "Counts for each counterbalanced block order.",
        args.overwrite_captions,
    )

    clip_inventory = blocks_pre[["participant_id", "block", "condition", "preset_id"]].copy()
    clip_inventory.to_csv(tdir / "Table2_clip_inventory.csv", index=False)
    write_caption(
        cdir / "Table2_clip_inventory.txt",
        "Clip inventory based on saved preset IDs (per participant block).",
        args.overwrite_captions,
    )

    # 4.2 Manipulation integrity
    sec_4_2 = ensure_dir(out_root / "4_2_manipulation")
    fdir = ensure_dir(sec_4_2 / "figures")
    cdir = ensure_dir(sec_4_2 / "captions")

    if not post_long.empty:
        expect = post_long[post_long["item_key"] == "B_7"].copy()
        if not expect.empty:
            fig, ax = plt.subplots(figsize=(6, 4))
            box_with_points(ax, expect, "score", "B_7: The revealed modality matched what I expected")
            save_figure(fig, fdir / "Figure1_expectation_match")
            write_caption(
                cdir / "Figure1_expectation_match.txt",
                "Expectation match after reveal by condition. B_7: The revealed modality matched what I expected.",
                args.overwrite_captions,
            )

    # 4.3 Solo study figures
    sec_4_3 = ensure_dir(out_root / "4_3_solo")
    fdir = ensure_dir(sec_4_3 / "figures")
    tdir = ensure_dir(sec_4_3 / "tables")
    cdir = ensure_dir(sec_4_3 / "captions")

    if not pre_long.empty:
        items = list(PRE_ITEMS.items())
        ncols = 3
        nrows = math.ceil(len(items) / ncols)
        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(12, 4 * nrows))
        axes = np.array(axes).reshape(-1)
        for ax, (key, item_label) in zip(axes, items):
            sub = pre_long[pre_long["item"] == item_label].copy()
            title = f"{key}: {PRE_QUESTIONS.get(key, item_label.replace('_',' ').title())}"
            box_with_points(ax, sub, "score", title)
        for ax in axes[len(items):]:
            ax.axis("off")
        save_figure(fig, fdir / "Figure2_pre_reveal_ratings")
        write_caption(
            cdir / "Figure2_pre_reveal_ratings.txt",
            "Pre-reveal ratings (Part A) by condition. Each panel shows the full question text.",
            args.overwrite_captions,
        )

    if not post_long.empty:
        fusion = blocks_post.copy()
        fusion["fusion_index"] = as_numeric(fusion.get("B_1")) + as_numeric(fusion.get("B_2"))
        fusion["fusion_index"] = fusion["fusion_index"] / 2.0
        fig, ax = plt.subplots(figsize=(6, 4))
        box_with_points(
            ax,
            fusion,
            "fusion_index",
            "Fusion/equality index (B_1 + B_2)",
        )
        save_figure(fig, fdir / "Figure3_fusion_equality")
        write_caption(
            cdir / "Figure3_fusion_equality.txt",
            "Fusion/equality index by condition. B_1: two views of the same process. B_2: sound/light balance.",
            args.overwrite_captions,
        )

        inter = blocks_post.copy()
        inter["constructive"] = as_numeric(inter.get("B_4"))
        inter["destructive"] = as_numeric(inter.get("B_5"))
        fig, ax = plt.subplots(figsize=(6, 4))
        for cond in COND_ORDER:
            sub = inter[inter["condition"] == cond]
            ax.scatter(sub["constructive"], sub["destructive"], label=COND_LABELS.get(cond, cond), alpha=0.7)
        ax.set_xlabel("B_4: Sound/light reinforced each other")
        ax.set_ylabel("B_5: Sound/light competed or contradicted")
        ax.legend(fontsize=8)
        ax.set_xlim(1, 7)
        ax.set_ylim(1, 7)
        ax.set_title("Interference profile by condition")
        save_figure(fig, fdir / "Figure4_interference_profile")
        write_caption(
            cdir / "Figure4_interference_profile.txt",
            "Constructive (B_4) vs destructive (B_5) interference ratings by condition.",
            args.overwrite_captions,
        )

        agency = blocks_pre.copy()
        agency["agency_index"] = (
            as_numeric(agency.get("A_2")) +
            as_numeric(agency.get("A_3")) +
            as_numeric(agency.get("A_4")) +
            (8 - as_numeric(agency.get("A_6")))
        ) / 4.0
        fig, ax = plt.subplots(figsize=(6, 4))
        box_with_points(
            ax,
            agency,
            "agency_index",
            "Agency/control index (A_2, A_3, A_4, reversed A_6)",
        )
        save_figure(fig, fdir / "Figure5_agency_control")
        write_caption(
            cdir / "Figure5_agency_control.txt",
            "Agency/control index by condition (A_2 intention clarity, A_3 steerability, A_4 interface understanding, A_6 reversed).",
            args.overwrite_captions,
        )

        novelty = blocks_pre.copy()
        novelty["novelty"] = as_numeric(novelty.get("A_5"))
        coherence = blocks_post.copy()
        coherence["coherence"] = as_numeric(coherence.get("B_3"))
        merged = novelty[["participant_id", "block", "condition", "novelty"]].merge(
            coherence[["participant_id", "block", "coherence"]],
            on=["participant_id", "block"],
            how="inner",
        )
        fig, ax = plt.subplots(figsize=(6, 4))
        for cond in COND_ORDER:
            sub = merged[merged["condition"] == cond]
            ax.scatter(sub["novelty"], sub["coherence"], label=COND_LABELS.get(cond, cond), alpha=0.7)
        ax.set_xlabel("A_5: Useful/interesting surprise (novelty proxy)")
        ax.set_ylabel("B_3: Coherence/legibility")
        ax.set_xlim(1, 7)
        ax.set_ylim(1, 7)
        ax.legend(fontsize=8)
        ax.set_title("Novelty vs coherence by condition")
        save_figure(fig, fdir / "Figure6_novelty_vs_coherence")
        write_caption(
            cdir / "Figure6_novelty_vs_coherence.txt",
            "Novelty proxy (A_5) vs coherence (B_3) by condition.",
            args.overwrite_captions,
        )

        exp = blocks_post.copy()
        exp["expectation"] = as_numeric(exp.get("B_7"))
        exp["interpretation_change"] = as_numeric(exp.get("B_8"))
        fig, ax = plt.subplots(figsize=(6, 4))
        for cond in COND_ORDER:
            sub = exp[exp["condition"] == cond]
            ax.scatter(sub["expectation"], sub["interpretation_change"], label=COND_LABELS.get(cond, cond), alpha=0.7)
        ax.set_xlabel("B_7: Revealed modality matched what I expected")
        ax.set_ylabel("B_8: Revealed modality changed interpretation")
        ax.set_xlim(1, 7)
        ax.set_ylim(1, 7)
        ax.legend(fontsize=8)
        ax.set_title("Expectation vs interpretation change")
        save_figure(fig, fdir / "Figure7_expectation_vs_interpretation")
        write_caption(
            cdir / "Figure7_expectation_vs_interpretation.txt",
            "Expectation match (B_7) vs interpretation change (B_8) by condition.",
            args.overwrite_captions,
        )

        # Block position effect (fusion index as a summary)
        fusion_pos = fusion[["participant_id", "block_position", "fusion_index"]].dropna()
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.boxplot(ax=ax, data=fusion_pos, x="block_position", y="fusion_index", showfliers=False)
        sns.stripplot(ax=ax, data=fusion_pos, x="block_position", y="fusion_index", color="black", size=3, jitter=0.2)
        ax.set_xlabel("Block position (1/2/3)")
        ax.set_ylabel("Fusion index")
        ax.set_ylim(1, 7)
        ax.set_title("Fusion by block position")
        save_figure(fig, fdir / "Figure8_block_position")
        write_caption(
            cdir / "Figure8_block_position.txt",
            "Fusion index by block position (learning/fatigue check).",
            args.overwrite_captions,
        )

        # Parameter influence frequency
        def normalize_param_list(val):
            if val is None or val == "":
                return []
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                return [v.strip() for v in val.split(",") if v.strip()]
            return []

        param_rows = []
        for _, row in blocks_post.iterrows():
            params = normalize_param_list(row.get("param_influence"))
            for p in params:
                param_rows.append({
                    "participant_id": row.get("participant_id"),
                    "block": row.get("block"),
                    "condition": row.get("condition"),
                    "parameter": p,
                })
        param_df = pd.DataFrame(param_rows)
        if not param_df.empty:
            param_counts = (
                param_df.groupby(["condition", "parameter"])
                .size()
                .reset_index(name="count")
                .sort_values(["condition", "count"], ascending=[True, False])
            )
            param_counts.to_csv(tdir / "Table3_parameter_influence.csv", index=False)
            write_caption(
                cdir / "Table3_parameter_influence.txt",
                "Frequency of participant-selected influential parameters by condition.",
                args.overwrite_captions,
            )

            fig, ax = plt.subplots(figsize=(8, 5))
            sns.barplot(ax=ax, data=param_counts, x="parameter", y="count", hue="condition")
            ax.set_xlabel("Parameter")
            ax.set_ylabel("Count")
            ax.set_title("Parameter influence frequency")
            ax.legend(
                title="Condition",
                labels=[COND_LABELS.get(c, c) for c in COND_ORDER],
                loc="upper right",
                frameon=True,
                fontsize=8,
            )
            ax.tick_params(axis="x", rotation=45)
            save_figure(fig, fdir / "Supplementary_parameter_influence")
            write_caption(
                cdir / "Supplementary_parameter_influence.txt",
                "Most-cited influential parameters by condition (supplementary).",
                args.overwrite_captions,
            )

        # Within-participant profiles (fusion index)
        if not fusion.empty:
            fig, ax = plt.subplots(figsize=(7, 4))
            for pid, grp in fusion.groupby("participant_id"):
                grp = grp.set_index("condition").reindex(COND_ORDER)
                ax.plot(COND_ORDER, grp["fusion_index"], marker="o", alpha=0.6, label=str(pid))
            ax.set_ylim(1, 7)
            ax.set_xlabel("Condition")
            ax.set_ylabel("Fusion index")
            ax.set_title("Within-participant fusion profiles")
            ax.set_xticks(range(len(COND_ORDER)))
            ax.set_xticklabels([COND_LABELS.get(c, c) for c in COND_ORDER])
            save_figure(fig, fdir / "Supplementary_within_participant_profiles")
            write_caption(
                cdir / "Supplementary_within_participant_profiles.txt",
                "Within-participant fusion profiles across conditions (supplementary).",
                args.overwrite_captions,
            )

    # 4.6 Participant background effects
    sec_4_6 = ensure_dir(out_root / "4_6_experience")
    fdir = ensure_dir(sec_4_6 / "figures")
    cdir = ensure_dir(sec_4_6 / "captions")

    if not blocks_post.empty and not background.empty:
        fusion = blocks_post.copy()
        fusion["fusion_index"] = (as_numeric(fusion.get("B_1")) + as_numeric(fusion.get("B_2"))) / 2.0
        fusion = merge_background_fields(
            fusion,
            background,
            ["musical_experience", "generative_experience"],
        )
        fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(10, 4))
        sns.stripplot(ax=axes[0], data=fusion, x="musical_experience", y="fusion_index", jitter=0.2)
        axes[0].set_title("Fusion by musical experience")
        axes[0].set_ylabel("Fusion index")
        axes[0].tick_params(axis="x", rotation=45)
        sns.stripplot(ax=axes[1], data=fusion, x="generative_experience", y="fusion_index", jitter=0.2)
        axes[1].set_title("Fusion by generative experience")
        axes[1].set_ylabel("Fusion index")
        axes[1].tick_params(axis="x", rotation=45)
        save_figure(fig, fdir / "Figure11_experience_groups")
        write_caption(
            cdir / "Figure11_experience_groups.txt",
            "Fusion index by musical and generative experience (exploratory).",
            args.overwrite_captions,
        )

    # 4.7 Qualitative (word cloud)
    sec_4_7 = ensure_dir(out_root / "4_7_qualitative")
    fdir = ensure_dir(sec_4_7 / "figures")
    cdir = ensure_dir(sec_4_7 / "captions")

    text_fields = []
    for col in ["strategy", "expectation_vs_outcome", "interference_notes", "reflection", "one_change"]:
        if col in sections_df.columns:
            text_fields.append(col)

    text_blobs: List[str] = []
    for col in text_fields:
        vals = sections_df[col].dropna().astype(str).tolist()
        text_blobs.extend(vals)

    if args.addendum_json.exists():
        addendum_data = json.loads(args.addendum_json.read_text(encoding="utf-8"))
        addendum_df = pd.DataFrame(addendum_data)
        for col in [
            "piece_title_favourite",
            "piece_description_one_line",
            "authorship_reason",
            "return_conditions",
            "remove_one_thing",
            "add_one_thing",
            "collaboration_reason",
        ]:
            if col in addendum_df.columns:
                text_blobs.extend(addendum_df[col].dropna().astype(str).tolist())

    if WORDCLOUD_AVAILABLE and text_blobs:
        text_all = " ".join(text_blobs)
        stopwords = set(STOPWORDS)
        stopwords.update(["like", "just", "really", "one", "also"])
        wc = WordCloud(width=1200, height=800, background_color="white", stopwords=stopwords)
        wc.generate(text_all)
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        save_figure(fig, fdir / "Supplementary_wordcloud")
        write_caption(
            cdir / "Supplementary_wordcloud.txt",
            "Word cloud from participant free-text responses (illustrative only).",
            args.overwrite_captions,
        )

    # 4.8 Addendum summary
    if args.addendum_json.exists():
        sec_4_8 = ensure_dir(out_root / "4_8_addendum")
        tdir = ensure_dir(sec_4_8 / "tables")
        cdir = ensure_dir(sec_4_8 / "captions")
        addendum_data = json.loads(args.addendum_json.read_text(encoding="utf-8"))
        addendum_df = pd.DataFrame(addendum_data)
        summary_rows = []
        for col in ["authorship_attribution", "target_user", "collaboration_expectation"]:
            if col in addendum_df.columns:
                counts = addendum_df[col].value_counts(dropna=False)
                for key, count in counts.items():
                    summary_rows.append({"field": col, "value": key, "count": int(count)})
        summary = pd.DataFrame(summary_rows)
        summary.to_csv(tdir / "Table6_addendum_summary.csv", index=False)
        write_caption(
            cdir / "Table6_addendum_summary.txt",
            "Addendum summary (selected categorical fields).",
            args.overwrite_captions,
        )

    # 4.9 Dyad summary
    if not dyad.empty:
        sec_4_9 = ensure_dir(out_root / "4_9_dyad")
        tdir = ensure_dir(sec_4_9 / "tables")
        cdir = ensure_dir(sec_4_9 / "captions")
        dyad_cols = [
            "participant_id",
            "dyad_id",
            "role",
            "dyad_preset_id",
            "D_1",
            "D_2",
            "D_3",
            "D_4",
            "D_5",
            "D_6",
            "D_7",
            "D_8",
            "communication_notes",
            "disagreements",
        ]
        dyad_out = dyad.reindex(columns=[c for c in dyad_cols if c in dyad.columns]).copy()
        dyad_out.to_csv(tdir / "Table7_dyad_responses.csv", index=False)
        write_caption(
            cdir / "Table7_dyad_responses.txt",
            "Dyad questionnaire responses (per participant).",
            args.overwrite_captions,
        )

    # Rater data (optional)
    manifest = None
    if args.manifest_csv.exists():
        try:
            manifest = pd.read_csv(args.manifest_csv)
        except Exception:
            manifest = None

    if args.rater_csv.exists():
        rater_df = pd.read_csv(args.rater_csv)
        if not rater_df.empty:
            if "payload_json" in rater_df.columns:
                rater_df["payload_dict"] = rater_df["payload_json"].apply(parse_payload_json)
                payload_expanded = pd.json_normalize(rater_df["payload_dict"])
                rater_df = pd.concat([rater_df.drop(columns=["payload_json"]), payload_expanded], axis=1)
            else:
                rater_df["payload_dict"] = [{} for _ in range(len(rater_df))]

            rater_rows = []
            for _, row in rater_df.iterrows():
                for key, label in RATER_MAP.items():
                    val = row.get(key)
                    if val is None or val == "":
                        continue
                    rater_rows.append({
                        "token": row.get("token"),
                        "clip_id": row.get("clip_id"),
                        "construct": label,
                        "score": float(val),
                    })
            rater_long = pd.DataFrame(rater_rows)

            # If manifest is present, merge condition
            if manifest is not None and "condition" in manifest.columns:
                cond_map = manifest[["clip_id", "condition"]].copy()
                cond_map["condition"] = cond_map["condition"].replace({
                    "A": "V", "B": "A", "C": "AV"
                })
                rater_long = rater_long.merge(cond_map, on="clip_id", how="left")

            # 4.4 baseline vs participant (if conditions exist)
            if "condition" in rater_long.columns:
                sec_4_4 = ensure_dir(out_root / "4_4_baseline")
                fdir = ensure_dir(sec_4_4 / "figures")
                cdir = ensure_dir(sec_4_4 / "captions")
                sub = rater_long[rater_long["construct"] == "preference"].dropna()
                if not sub.empty:
                    fig, ax = plt.subplots(figsize=(6, 4))
                    sns.boxplot(ax=ax, data=sub, x="condition", y="score", showfliers=False)
                    sns.stripplot(ax=ax, data=sub, x="condition", y="score", color="black", size=3, jitter=0.2)
                    ax.set_ylim(1, 7)
                    ax.set_title("Rater preference by condition")
                    save_figure(fig, fdir / "Figure9_rater_preference_by_condition")
                    write_caption(
                        cdir / "Figure9_rater_preference_by_condition.txt",
                        "Rater preference by condition (if manifest provides condition labels).",
                        args.overwrite_captions,
                    )

            # 4.5 cross-link (self vs rater)
            sec_4_5 = ensure_dir(out_root / "4_5_crosslink")
            fdir = ensure_dir(sec_4_5 / "figures")
            cdir = ensure_dir(sec_4_5 / "captions")
            if not rater_long.empty and not blocks_post.empty:
                # Use fusion index for self vs rater fusion
                fusion_self = blocks_post.copy()
                fusion_self["fusion_index"] = (as_numeric(fusion_self.get("B_1")) + as_numeric(fusion_self.get("B_2"))) / 2.0
                fusion_self = fusion_self[["participant_id", "block", "fusion_index", "preset_id"]].copy()
                # No direct clip_id link in participant data; use preset_id if manifest contains it
                if manifest is not None and "preset_id" in manifest.columns:
                    preset_map = manifest[["clip_id", "preset_id"]].dropna()
                    fusion_self = fusion_self.merge(preset_map, on="preset_id", how="left")
                # Aggregate rater fusion by clip
                rater_fusion = rater_long[rater_long["construct"] == "fusion"].groupby("clip_id")["score"].mean().reset_index()
                if "clip_id" in fusion_self.columns:
                    merged = fusion_self.merge(rater_fusion, on="clip_id", how="inner")
                    if not merged.empty:
                        fig, ax = plt.subplots(figsize=(5, 4))
                        ax.scatter(merged["fusion_index"], merged["score"], alpha=0.7)
                        ax.set_xlabel("Participant fusion index")
                        ax.set_ylabel("Rater fusion mean")
                        ax.set_title("Self vs rater fusion")
                        save_figure(fig, fdir / "Figure10_self_vs_rater_fusion")
                        write_caption(
                            cdir / "Figure10_self_vs_rater_fusion.txt",
                            "Participant fusion index vs rater fusion mean (linked by preset_id when available).",
                            args.overwrite_captions,
                        )

    print(f"Outputs written to: {out_root.resolve()}")


def main() -> None:
    args = parse_args()
    build_outputs(args)


if __name__ == "__main__":
    main()
