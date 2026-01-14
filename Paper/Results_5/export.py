from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt

SIZE_PRESETS = {
    "single": (3.35, 2.6),
    "double": (6.9, 4.2),
}


def apply_size(fig: plt.Figure, size_key: str | None, scale: tuple[float, float]) -> None:
    if size_key is None:
        return
    size = SIZE_PRESETS.get(size_key, SIZE_PRESETS["double"])
    fig.set_size_inches(size[0] * scale[0], size[1] * scale[1])


def save_figure(
    fig: plt.Figure,
    out_base: str,
    size_key: str,
    make_tif: bool = True,
    size_scale: tuple[float, float] = (1.0, 1.0),
    bbox_inches: str | None = "tight",
) -> List[str]:
    apply_size(fig, size_key, size_scale)
    base = Path(out_base)
    base.parent.mkdir(parents=True, exist_ok=True)

    paths: List[str] = []
    eps_path = str(base.with_suffix(".eps"))
    pdf_path = str(base.with_suffix(".pdf"))
    png_path = str(base.with_suffix(".png"))
    fig.savefig(eps_path, bbox_inches=bbox_inches)
    fig.savefig(pdf_path, bbox_inches=bbox_inches)
    fig.savefig(png_path, dpi=300, bbox_inches=bbox_inches)
    paths.extend([eps_path, pdf_path, png_path])

    if make_tif:
        tif_path = str(base.with_suffix(".tif"))
        fig.savefig(tif_path, dpi=600, bbox_inches=bbox_inches)
        paths.append(tif_path)
    return paths
