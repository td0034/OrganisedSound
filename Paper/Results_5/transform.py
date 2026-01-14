from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import CONDITION_LABELS, CONDITION_ORDER, CONSTRUCTS, END_ITEM_LABELS, ITEMS, KNOWN_PARAMS
from io_ingest import parse_order_string


ITEM_TO_CONSTRUCT: Dict[str, str] = {}
for construct, meta in CONSTRUCTS.items():
    for item in meta.get("items", []):
        ITEM_TO_CONSTRUCT[item] = construct


def to_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def reverse_code(value: Optional[float], scale_min: int = 1, scale_max: int = 7) -> Optional[float]:
    if value is None or np.isnan(value):
        return None
    return scale_max + scale_min - float(value)


def build_participants_df(records: List[Dict[str, Any]]) -> pd.DataFrame:
    background_rows = []
    meta_rows = []
    for rec in records:
        pid = rec.get("participant_id")
        section = rec.get("section_key")
        payload = rec.get("payload") or {}
        if section == "background":
            background_rows.append({"participant_id": pid, **payload})
        elif section == "meta":
            meta_rows.append({"participant_id": pid, **payload})
    background_df = pd.DataFrame(background_rows)
    meta_df = pd.DataFrame(meta_rows)
    if background_df.empty:
        participants_df = meta_df
    else:
        participants_df = background_df.merge(meta_df, on="participant_id", how="left")
    return participants_df


def build_order_map(participants_df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    order_map: Dict[str, Dict[str, int]] = {}
    if participants_df.empty or "order" not in participants_df.columns:
        return order_map
    for _, row in participants_df.iterrows():
        pid = row.get("participant_id")
        order_raw = row.get("order")
        if not pid:
            continue
        letters = parse_order_string(order_raw)
        order_map[pid] = {cond: i + 1 for i, cond in enumerate(letters)}
    return order_map


def build_end_df(records: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for rec in records:
        if rec.get("section_key") != "end":
            continue
        payload = rec.get("payload") or {}
        rows.append({"participant_id": rec.get("participant_id"), **payload})
    end_df = pd.DataFrame(rows)
    for col in ["rank_A", "rank_B", "rank_C"]:
        if col in end_df.columns:
            end_df[col] = pd.to_numeric(end_df[col], errors="coerce")
    return end_df


def build_blocks_long(records: List[Dict[str, Any]], order_map: Dict[str, Dict[str, int]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for rec in records:
        section = rec.get("section_key") or ""
        match = re.match(r"block_([ABC])_(pre|post)$", section)
        if match:
            condition, phase = match.groups()
            payload = rec.get("payload") or {}
            for item, meta in ITEMS.items():
                if meta.get("phase") != phase:
                    continue
                raw_value = payload.get(item)
                value = to_numeric(raw_value)
                rows.append({
                    "participant_id": rec.get("participant_id"),
                    "condition": condition,
                    "phase": phase,
                    "item": item,
                    "value": value,
                    "item_label": meta.get("label"),
                    "is_reverse": bool(meta.get("direction", 1) == -1),
                    "construct": ITEM_TO_CONSTRUCT.get(item),
                    "block_position": order_map.get(rec.get("participant_id"), {}).get(condition),
                    "timestamps": rec.get("updated_at"),
                })
            continue

        if section == "end":
            payload = rec.get("payload") or {}
            for cond in CONDITION_ORDER:
                key = f"rank_{cond}"
                if key in payload:
                    rows.append({
                        "participant_id": rec.get("participant_id"),
                        "condition": cond,
                        "phase": "end",
                        "item": "rank",
                        "value": to_numeric(payload.get(key)),
                        "item_label": END_ITEM_LABELS.get("rank"),
                        "is_reverse": False,
                        "construct": None,
                        "block_position": order_map.get(rec.get("participant_id"), {}).get(cond),
                        "timestamps": rec.get("updated_at"),
                    })
            for key in ("most_intermedial", "biggest_mismatch"):
                val = payload.get(key)
                if val in CONDITION_ORDER:
                    rows.append({
                        "participant_id": rec.get("participant_id"),
                        "condition": val,
                        "phase": "end",
                        "item": key,
                        "value": 1.0,
                        "item_label": END_ITEM_LABELS.get(key),
                        "is_reverse": False,
                        "construct": None,
                        "block_position": order_map.get(rec.get("participant_id"), {}).get(val),
                        "timestamps": rec.get("updated_at"),
                    })

    return pd.DataFrame(rows)


def build_blocks_wide(records: List[Dict[str, Any]], order_map: Dict[str, Dict[str, int]]) -> pd.DataFrame:
    pre_rows: Dict[Tuple[str, str], Dict[str, Any]] = {}
    post_rows: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for rec in records:
        section = rec.get("section_key") or ""
        match = re.match(r"block_([ABC])_(pre|post)$", section)
        if not match:
            continue
        condition, phase = match.groups()
        pid = rec.get("participant_id")
        payload = rec.get("payload") or {}
        key = (pid, condition)
        base = {
            "participant_id": pid,
            "condition": condition,
            "condition_label": CONDITION_LABELS.get(condition, condition),
            "block_position": order_map.get(pid, {}).get(condition),
        }
        if phase == "pre":
            row = pre_rows.setdefault(key, base.copy())
            for item, meta in ITEMS.items():
                if meta.get("phase") == "pre":
                    row[item] = to_numeric(payload.get(item))
            row["aim"] = payload.get("aim")
            row["strategy"] = payload.get("strategy")
            row["preset_id"] = payload.get("preset_id")
            row["timestamp_pre"] = rec.get("updated_at")
        else:
            row = post_rows.setdefault(key, base.copy())
            for item, meta in ITEMS.items():
                if meta.get("phase") == "post":
                    row[item] = to_numeric(payload.get(item))
            row["param_influence"] = payload.get("param_influence")
            row["param_other"] = payload.get("param_other")
            row["expectation_vs_outcome"] = payload.get("expectation_vs_outcome")
            row["interference_notes"] = payload.get("interference_notes")
            row["preset_id"] = payload.get("preset_id")
            row["timestamp_post"] = rec.get("updated_at")

    rows = []
    for key in sorted(set(pre_rows) | set(post_rows)):
        row = {}
        row.update(pre_rows.get(key, {}))
        row.update(post_rows.get(key, {}))
        rows.append(row)

    wide_df = pd.DataFrame(rows)
    return compute_composites(wide_df)


def compute_composites(wide_df: pd.DataFrame) -> pd.DataFrame:
    if wide_df.empty:
        return wide_df
    for construct, meta in CONSTRUCTS.items():
        items = [i for i in meta.get("items", []) if i in wide_df.columns]
        if not items:
            continue
        tmp = wide_df[items].copy()
        for item in meta.get("reverse", []):
            if item in tmp.columns:
                tmp[item] = tmp[item].apply(reverse_code)
        wide_df[construct] = tmp.mean(axis=1, skipna=True)
    return wide_df


def normalize_param_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except Exception:
                pass
        return [part.strip() for part in s.split(",") if part.strip()]
    return []


def build_param_counts(wide_df: pd.DataFrame) -> pd.DataFrame:
    if wide_df.empty or "param_influence" not in wide_df.columns:
        return pd.DataFrame(columns=["condition", "parameter", "count", "percent"])
    rows = []
    for _, row in wide_df.iterrows():
        params = normalize_param_list(row.get("param_influence"))
        if row.get("param_other"):
            params.append("Other")
        for param in params:
            rows.append({
                "condition": row.get("condition"),
                "parameter": param,
            })
    if not rows:
        return pd.DataFrame(columns=["condition", "parameter", "count", "percent"])
    df = pd.DataFrame(rows)
    counts = df.groupby(["condition", "parameter"]).size().reset_index(name="count")
    total = counts.groupby("condition")["count"].transform("sum")
    counts["percent"] = counts["count"] / total * 100.0
    return counts


def find_unknown_params(param_counts: pd.DataFrame) -> List[str]:
    if param_counts.empty:
        return []
    params = sorted(set(param_counts["parameter"]) - set(KNOWN_PARAMS) - {"Other"})
    return params


def build_missingness_report(long_df: pd.DataFrame) -> pd.DataFrame:
    if long_df.empty:
        return long_df
    df = long_df[long_df["phase"].isin(["pre", "post"])].copy()
    df["is_missing"] = df["value"].isna()
    report = df.groupby(["participant_id", "condition", "phase", "item"], dropna=False).agg(
        n_missing=("is_missing", "sum"),
        n_total=("is_missing", "count"),
    ).reset_index()
    totals = report.groupby(["participant_id", "condition", "phase"], dropna=False).agg(
        n_missing=("n_missing", "sum"),
        n_total=("n_total", "sum"),
    ).reset_index()
    totals["item"] = "__TOTAL__"
    report = pd.concat([report, totals], ignore_index=True)
    return report
