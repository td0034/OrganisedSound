#!/usr/bin/env python3
"""Generate 9x3 montage snapshots (plus participant column) from rotated clips."""

from __future__ import annotations

import argparse
import random
import re
import subprocess
import sys
from pathlib import Path

CONDITION_ORDER = ["A", "B", "C"]
PARTICIPANT_HEADER = "Participant ID"
LABELS = {
    "A": "A - Visual Only",
    "B": "B - Audio Only",
    "C": "C - Both Modalities",
}
FILENAME_RE = re.compile(r"^(?P<participant>[^_]+)_(?P<condition>[ABC])_")


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[1]
    default_input = repo_root / "Rater Survey" / "rotated_clips"
    default_output = script_dir / "output"

    parser = argparse.ArgumentParser(
        description="Create 9x3 montage images from rater survey clips.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=default_input,
        help=f"Input directory of rotated clips (default: {default_input})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help=f"Output directory for montages (default: {default_output})",
    )
    parser.add_argument(
        "--times",
        default="15,30,45",
        help="Comma-separated list of snapshot times in seconds (default: 15,30,45)",
    )
    parser.add_argument(
        "--every-second",
        action="store_true",
        help="Generate a montage for every whole second up to the shortest clip",
    )
    parser.add_argument("--cell-width", type=int, default=240, help="Thumbnail cell width")
    parser.add_argument("--cell-height", type=int, default=240, help="Thumbnail cell height")
    parser.add_argument(
        "--label-width",
        type=int,
        default=0,
        help="Participant column width (0 uses cell width)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Multiply cell size, header height, and font size by this factor",
    )
    parser.add_argument("--header-height", type=int, default=56, help="Header band height")
    parser.add_argument("--font-size", type=int, default=24, help="Header label font size")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for row ordering (default: random)",
    )
    parser.add_argument(
        "--no-shuffle",
        action="store_true",
        help="Do not randomize row order",
    )
    parser.add_argument(
        "--no-rotate",
        action="store_true",
        help="Skip 180-degree rotation if clips are already corrected",
    )
    return parser.parse_args()


def parse_times(times_value: str) -> list[float]:
    times = []
    for chunk in times_value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            times.append(float(chunk))
        except ValueError as exc:
            raise ValueError(f"Invalid time value: {chunk}") from exc
    if not times:
        raise ValueError("No valid times provided")
    return times


def time_label(seconds: float) -> str:
    if float(seconds).is_integer():
        return f"{int(seconds)}s"
    return f"{str(seconds).replace('.', 'p')}s"


def run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        print(result.stdout)
        raise RuntimeError("ffmpeg failed")


def run_ffprobe(args: list[str]) -> str:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        print(result.stdout)
        raise RuntimeError("ffprobe failed")
    return result.stdout.strip()


def collect_videos(input_dir: Path) -> dict[str, dict[str, Path]]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    participants: dict[str, dict[str, Path]] = {}
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() != ".mp4":
            continue
        match = FILENAME_RE.match(path.name)
        if not match:
            continue
        participant = match.group("participant")
        condition = match.group("condition")
        participants.setdefault(participant, {})[condition] = path

    if not participants:
        raise ValueError(f"No matching clips found in {input_dir}")
    return participants


def validate_participants(participants: dict[str, dict[str, Path]]) -> None:
    missing = {}
    for participant, clips in participants.items():
        needed = [c for c in CONDITION_ORDER if c not in clips]
        if needed:
            missing[participant] = needed

    if missing:
        details = ", ".join(
            f"{participant}: {''.join(needed)}" for participant, needed in missing.items()
        )
        raise ValueError(f"Missing clips for participants: {details}")


def write_row_order(output_dir: Path, participants: list[str]) -> None:
    order_path = output_dir / "row_order.txt"
    lines = [
        f"Row {idx + 1} (ID {idx + 1}): {participant}"
        for idx, participant in enumerate(participants)
    ]
    order_path.write_text("\n".join(lines) + "\n")


def build_layout(cell_width: int, cell_height: int, total_inputs: int) -> str:
    layout = []
    for idx in range(total_inputs):
        col = idx % len(CONDITION_ORDER)
        row = idx // len(CONDITION_ORDER)
        layout.append(f"{col * cell_width}_{row * cell_height}")
    return "|".join(layout)


def generate_thumbnails(
    clips: dict[str, dict[str, Path]],
    participants: list[str],
    output_dir: Path,
    snapshot_time: float,
    cell_width: int,
    cell_height: int,
    rotate: bool,
) -> list[Path]:
    thumb_dir = output_dir / f"thumbs_{time_label(snapshot_time)}"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    thumbs: list[Path] = []
    for row_idx, participant in enumerate(participants, start=1):
        for condition in CONDITION_ORDER:
            clip_path = clips[participant][condition]
            thumb_path = thumb_dir / f"{row_idx:02d}_{participant}_{condition}.png"
            vf_parts = []
            if rotate:
                vf_parts.extend(["hflip", "vflip"])
            vf_parts.append(
                f"scale={cell_width}:{cell_height}:force_original_aspect_ratio=increase"
            )
            vf_parts.append(f"crop={cell_width}:{cell_height}")
            vf = ",".join(vf_parts)

            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(snapshot_time),
                "-i",
                str(clip_path),
                "-frames:v",
                "1",
                "-an",
                "-vf",
                vf,
                "-y",
                str(thumb_path),
            ]
            run_ffmpeg(cmd)
            thumbs.append(thumb_path)

    return thumbs


def escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def probe_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        str(path),
    ]
    output = run_ffprobe(cmd)
    return float(output)


def assemble_montage(
    thumbnails: list[Path],
    output_path: Path,
    cell_width: int,
    cell_height: int,
    header_height: int,
    font_size: int,
    label_width: int,
    participant_labels: list[str],
) -> None:
    total_inputs = len(thumbnails)
    layout = build_layout(cell_width, cell_height, total_inputs)

    draws = []
    header_labels = [PARTICIPANT_HEADER] + [LABELS[c] for c in CONDITION_ORDER]
    for idx, label in enumerate(header_labels):
        if idx == 0:
            col_x = 0
            col_width = label_width
        else:
            col_x = label_width + (idx - 1) * cell_width
            col_width = cell_width
        x_expr = f"{col_x}+({col_width}-text_w)/2"
        y_expr = f"({header_height}-text_h)/2"
        draws.append(
            "drawtext="
            f"text='{escape_drawtext(label)}':x={x_expr}:y={y_expr}"
            f":fontsize={font_size}:fontcolor=black"
        )

    for row_idx, participant in enumerate(participant_labels):
        y_expr = (
            f"{header_height}+({cell_height}*{row_idx})+({cell_height}-text_h)/2"
        )
        x_expr = f"({label_width}-text_w)/2"
        draws.append(
            "drawtext="
            f"text='{escape_drawtext(participant)}':x={x_expr}:y={y_expr}"
            f":fontsize={font_size}:fontcolor=black"
        )

    filter_complex = (
        f"xstack=inputs={total_inputs}:layout={layout}[grid];"
        f"[grid]pad=iw+{label_width}:ih+{header_height}:{label_width}:{header_height}"
        f":color=white[pad];"
        f"[pad]{','.join(draws)}"
    )

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
    for thumb in thumbnails:
        cmd += ["-i", str(thumb)]
    cmd += [
        "-filter_complex",
        filter_complex,
        "-frames:v",
        "1",
        "-y",
        str(output_path),
    ]
    run_ffmpeg(cmd)


def main() -> int:
    args = parse_args()

    if args.scale <= 0:
        print("Scale must be greater than 0", file=sys.stderr)
        return 2

    cell_width = max(1, int(args.cell_width * args.scale))
    cell_height = max(1, int(args.cell_height * args.scale))
    header_height = max(1, int(args.header_height * args.scale))
    font_size = max(1, int(args.font_size * args.scale))
    label_width = max(1, int(args.label_width * args.scale)) if args.label_width else cell_width

    try:
        clips = collect_videos(args.input_dir)
        validate_participants(clips)
    except (ValueError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        return 2

    participants = sorted(clips.keys())

    rng = random.Random(args.seed)
    if not args.no_shuffle:
        rng.shuffle(participants)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_row_order(args.output_dir, participants)
    participant_labels = [str(idx + 1) for idx in range(len(participants))]

    if args.every_second:
        clip_paths = [path for per in clips.values() for path in per.values()]
        try:
            min_duration = min(probe_duration(path) for path in clip_paths)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2
        if min_duration <= 0:
            print("Unable to determine clip durations", file=sys.stderr)
            return 2
        max_second = int(min_duration)
        times = [float(sec) for sec in range(0, max_second + 1)]
    else:
        try:
            times = parse_times(args.times)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2

    for snapshot_time in times:
        thumbs = generate_thumbnails(
            clips,
            participants,
            args.output_dir,
            snapshot_time,
            cell_width,
            cell_height,
            rotate=not args.no_rotate,
        )
        output_path = args.output_dir / f"montage_{time_label(snapshot_time)}.png"
        assemble_montage(
            thumbs,
            output_path,
            cell_width,
            cell_height,
            header_height,
            font_size,
            label_width,
            participant_labels,
        )
        print(f"Wrote {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
