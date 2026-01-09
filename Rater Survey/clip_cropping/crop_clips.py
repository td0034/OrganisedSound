#!/usr/bin/env python3
import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXTS = {".mp4", ".m4v", ".mov"}
CROP_FILTER = "crop=min(iw\\,ih):min(iw\\,ih):(iw-min(iw\\,ih))/2:(ih-min(iw\\,ih))/2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crop video clips to a centered square using ffmpeg."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("Rater Survey/clips"),
        help="Directory containing source clips.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Rater Survey/clips_square"),
        help="Directory for cropped clips.",
    )
    parser.add_argument(
        "--manifest-in",
        type=Path,
        default=None,
        help="Path to manifest.csv (defaults to <input-dir>/manifest.csv if present).",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=None,
        help="Path to write the migrated manifest (defaults to <output-dir>/manifest.csv).",
    )
    parser.add_argument(
        "--manifest-prefix",
        type=str,
        default="",
        help="Optional prefix to prepend to each manifest filepath (e.g., 'clips_square/').",
    )
    parser.add_argument(
        "--ffmpeg",
        type=str,
        default="ffmpeg",
        help="ffmpeg executable (default: ffmpeg).",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="CRF value for libx264 encoding (lower = higher quality).",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="medium",
        help="libx264 preset (e.g., veryfast, fast, medium, slow).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing outputs.",
    )
    parser.add_argument(
        "--skip-manifest",
        action="store_true",
        help="Skip manifest migration even if manifest.csv exists.",
    )
    return parser.parse_args()


def ensure_ffmpeg(ffmpeg_bin: str) -> None:
    if shutil.which(ffmpeg_bin) is None:
        raise FileNotFoundError(
            f"ffmpeg executable not found: {ffmpeg_bin}. Install ffmpeg or pass --ffmpeg PATH."
        )


def list_videos(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    return sorted(
        [
            p
            for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS
        ],
        key=lambda p: p.name,
    )


def build_ffmpeg_command(
    ffmpeg_bin: str,
    src: Path,
    dst: Path,
    crf: int,
    preset: str,
    overwrite: bool,
) -> list[str]:
    overwrite_flag = "-y" if overwrite else "-n"
    return [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        overwrite_flag,
        "-i",
        str(src),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-vf",
        CROP_FILTER,
        "-c:v",
        "libx264",
        "-crf",
        str(crf),
        "-preset",
        preset,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(dst),
    ]


def normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    prefix = prefix.replace("\\", "/")
    return prefix if prefix.endswith("/") else f"{prefix}/"


def migrate_manifest(
    manifest_in: Path,
    manifest_out: Path,
    manifest_prefix: str,
    input_files: set[str],
) -> None:
    with manifest_in.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        if "filepath" not in fieldnames:
            raise ValueError(f"manifest.csv missing 'filepath' column: {manifest_in}")
        rows = list(reader)

    prefix = normalize_prefix(manifest_prefix)
    updated_rows = []
    missing_files = []

    for row in rows:
        original = row.get("filepath", "")
        filename = Path(original).name
        if filename and filename not in input_files:
            missing_files.append(filename)
        row["filepath"] = f"{prefix}{filename}" if filename else original
        updated_rows.append(row)

    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    with manifest_out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    if missing_files:
        missing_preview = ", ".join(missing_files[:8])
        suffix = "..." if len(missing_files) > 8 else ""
        print(
            f"Warning: {len(missing_files)} manifest entries not found in input-dir: "
            f"{missing_preview}{suffix}",
            file=sys.stderr,
        )


def main() -> int:
    args = parse_args()

    try:
        ensure_ffmpeg(args.ffmpeg)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    input_dir = args.input_dir
    output_dir = args.output_dir
    if input_dir.resolve() == output_dir.resolve():
        print("Output directory must be different from input directory.", file=sys.stderr)
        return 1
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        videos = list_videos(input_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not videos:
        print(f"No video files found in {input_dir}", file=sys.stderr)
        return 1

    processed = 0
    skipped = 0

    for src in videos:
        dst = output_dir / src.name
        if dst.exists() and not args.overwrite:
            skipped += 1
            continue
        cmd = build_ffmpeg_command(
            args.ffmpeg, src, dst, args.crf, args.preset, args.overwrite
        )
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            print(f"ffmpeg failed for {src}: {exc}", file=sys.stderr)
            return exc.returncode
        processed += 1

    if not args.skip_manifest:
        manifest_in = args.manifest_in
        if manifest_in is None:
            candidate = input_dir / "manifest.csv"
            if candidate.exists():
                manifest_in = candidate

        if manifest_in is not None and manifest_in.exists():
            manifest_out = args.manifest_out or (output_dir / "manifest.csv")
            input_names = {p.name for p in videos}
            try:
                migrate_manifest(
                    manifest_in,
                    manifest_out,
                    args.manifest_prefix,
                    input_names,
                )
            except (OSError, ValueError) as exc:
                print(f"Manifest migration failed: {exc}", file=sys.stderr)
                return 1
        else:
            print("Manifest not found; skipping manifest migration.", file=sys.stderr)

    print(
        f"Done. Cropped {processed} clip(s). "
        f"Skipped {skipped} existing clip(s). Output: {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
