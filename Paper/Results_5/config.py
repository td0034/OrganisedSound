from __future__ import annotations

from typing import Dict, List

CONDITION_LABELS: Dict[str, str] = {
    "A": "Visual Only",
    "B": "Audio Only",
    "C": "Audiovisual",
}
CONDITION_ORDER: List[str] = ["A", "B", "C"]

LIKERT_SCALE: List[int] = [1, 2, 3, 4, 5, 6, 7]

ITEMS: Dict[str, Dict[str, object]] = {
    "A_1": {"label": "A1 satisfaction", "direction": 1, "phase": "pre"},
    "A_2": {"label": "A2 intention clarity", "direction": 1, "phase": "pre"},
    "A_3": {"label": "A3 steerability", "direction": 1, "phase": "pre"},
    "A_4": {"label": "A4 interface workable", "direction": 1, "phase": "pre"},
    "A_5": {"label": "A5 useful surprise", "direction": 1, "phase": "pre"},
    "A_6": {"label": "A6 frustrating unpredictability", "direction": -1, "phase": "pre"},
    "A_7": {"label": "A7 others would find interesting", "direction": 1, "phase": "pre"},
    "B_1": {"label": "B1 same-process", "direction": 1, "phase": "post"},
    "B_2": {"label": "B2 balanced modalities", "direction": 1, "phase": "post"},
    "B_3": {"label": "B3 coherent/legible relationship", "direction": 1, "phase": "post"},
    "B_4": {"label": "B4 constructive interference", "direction": 1, "phase": "post"},
    "B_5": {"label": "B5 destructive interference", "direction": -1, "phase": "post"},
    "B_6": {"label": "B6 overload", "direction": -1, "phase": "post"},
    "B_7": {"label": "B7 expectation match", "direction": 1, "phase": "post"},
    "B_8": {"label": "B8 interpretation change", "direction": 1, "phase": "post"},
    "B_9": {"label": "B9 plausible causal story", "direction": 1, "phase": "post"},
    "B_10": {"label": "B10 system autonomy", "direction": 1, "phase": "post"},
    "B_11": {"label": "B11 relied on visual cues", "direction": 1, "phase": "post"},
    "B_12": {"label": "B12 relied on theory cues", "direction": 1, "phase": "post"},
}

CONSTRUCTS: Dict[str, Dict[str, object]] = {
    "Intermediality Index": {
        "items": ["B_1", "B_2", "B_3", "B_4", "B_5", "B_6"],
        "reverse": ["B_5", "B_6"],
        "formula": "mean(reverse-coded B1-B6)",
        "interpretation": "Higher values indicate stronger intermedial coherence",
    },
    "Agency Index": {
        "items": ["A_2", "A_3", "A_4", "A_6"],
        "reverse": ["A_6"],
        "formula": "mean(reverse-coded A2-A4 minus A6)",
        "interpretation": "Higher values indicate stronger perceived agency",
    },
    "Mismatch Index": {
        "items": ["B_7", "B_8"],
        "reverse": [],
        "formula": "mean(B7, B8)",
        "interpretation": "Higher values indicate stronger expectation shifts",
    },
}

END_ITEM_LABELS: Dict[str, str] = {
    "rank": "Preference rank (1=best)",
    "most_intermedial": "Most intermedial",
    "biggest_mismatch": "Biggest mismatch",
}

KNOWN_PARAMS: List[str] = [
    "Rate",
    "Loop On/Off",
    "Loop Length",
    "Life Length",
    "Min Population",
    "Max Population",
    "Neighbourhood (Local/Extended)",
    "Min Neighbours",
    "Max Neighbours",
    "Scale",
]
