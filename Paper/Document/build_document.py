#!/usr/bin/env python3
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SECTION_FILES = [
    "0_Abstract",
    "1_Introduction",
    "2_Related Work",
    "3_Method",
    "4_Results",
    "5_Discussion",
    "6_Conclusion",
    "7_Acknowledgements",
    "8_References",
]

PDF_ENGINES = ["xelatex", "lualatex", "pdflatex", "tectonic"]


def title_from_filename(name):
    if "_" in name:
        name = name.split("_", 1)[1]
    return name.replace("_", " ").strip()


def first_nonempty_line(text):
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def needs_heading(text):
    line = first_nonempty_line(text)
    if not line:
        return True
    if re.match(r"^#+\s", line):
        return False
    if re.match(r"^\d+(\.\d+)*\.\s", line):
        return False
    return True


def next_run_dir(output_root):
    output_root.mkdir(exist_ok=True)
    pattern = re.compile(r"^run_(\d{3})$")
    max_num = 0
    for child in output_root.iterdir():
        if child.is_dir():
            match = pattern.match(child.name)
            if match:
                max_num = max(max_num, int(match.group(1)))
    return output_root / f"run_{max_num + 1:03d}"


def run_pandoc(args):
    try:
        subprocess.run(args, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"pandoc failed: {exc}", file=sys.stderr)
        return False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Merge paper sections and optionally export docx/pdf."
    )
    parser.add_argument(
        "--docx",
        action="store_true",
        help="Export a DOCX file (requires pandoc).",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Export a PDF file (requires pandoc and a PDF engine).",
    )
    parser.add_argument(
        "--pdf-engine",
        default="",
        help="Explicit PDF engine (overrides auto-detect).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    script_path = Path(__file__).resolve()
    doc_dir = script_path.parent
    paper_dir = doc_dir.parent

    output_root = doc_dir / "outputs"
    run_dir = next_run_dir(output_root)
    run_dir.mkdir(parents=True, exist_ok=False)

    merged_path = run_dir / "merged.md"

    pieces = []
    missing = []
    for name in SECTION_FILES:
        section_path = paper_dir / name
        if not section_path.exists():
            missing.append(section_path)
            continue
        text = section_path.read_text(encoding="utf-8").strip()
        if needs_heading(text):
            pieces.append(f"# {title_from_filename(name)}\n")
        if text:
            pieces.append(text)
        pieces.append("")

    merged_content = "\n".join(pieces).rstrip() + "\n"
    merged_path.write_text(merged_content, encoding="utf-8")
    print(f"Wrote {merged_path}")

    if missing:
        print("Missing sections:", file=sys.stderr)
        for path in missing:
            print(f" - {path}", file=sys.stderr)

    if not args.docx and not args.pdf:
        return

    pandoc = shutil.which("pandoc")
    if not pandoc:
        print("pandoc not found; skipping export.", file=sys.stderr)
        return

    resource_args = ["--resource-path", str(paper_dir)]

    if args.docx:
        docx_path = run_dir / "merged.docx"
        run_pandoc([pandoc, str(merged_path), *resource_args, "-o", str(docx_path)])

    if args.pdf:
        if args.pdf_engine:
            pdf_engine = args.pdf_engine
        else:
            pdf_engine = next((e for e in PDF_ENGINES if shutil.which(e)), None)
        if not pdf_engine:
            print(
                "No PDF engine found (xelatex/lualatex/pdflatex/tectonic). Skipping PDF.",
                file=sys.stderr,
            )
            return
        pdf_path = run_dir / "merged.pdf"
        run_pandoc(
            [
                pandoc,
                str(merged_path),
                *resource_args,
                "--pdf-engine",
                pdf_engine,
                "-o",
                str(pdf_path),
            ]
        )


if __name__ == "__main__":
    main()
