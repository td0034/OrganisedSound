#!/usr/bin/env python3
"""Build a clean markdown from the extracted docx text, with inline figures, then convert to PDF."""

import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIGS_DIR = BASE / "figures_pdf"

# Map paper figure numbers to PDF filenames
FIGURE_MAP = {
    1: "fig1.pdf",
    2: "fig2.pdf",
    3: "fig3.pdf",
    4: "fig4.pdf",
    5: "fig5.pdf",
    6: "fig6.pdf",
    7: "fig7.pdf",
    8: "fig8.pdf",
}

# Read the pandoc-extracted markdown
md_text = Path("/tmp/OS_Didiot.md").read_text()

# Clean up RTL quote artifacts from docx
md_text = md_text.replace('["\u200f]{dir="rtl"}', '"')
md_text = md_text.replace('["]{dir="rtl"}', '"')

# Clean up underline spans from docx
md_text = re.sub(r'\[([^\]]+)\]\{\.underline\}', r'\1', md_text)

# Process line by line: handle figure and video placeholders
lines = md_text.split('\n')
output_lines = []
i = 0
while i < len(lines):
    line = lines[i]

    # Match "Insert Figure X here"
    fig_match = re.match(r'^Insert Figure (\d+) here\.?$', line.strip())
    if fig_match:
        fig_num = int(fig_match.group(1))
        if fig_num in FIGURE_MAP:
            img_path = FIGS_DIR / FIGURE_MAP[fig_num]
            # Skip blank line after placeholder
            if i + 1 < len(lines) and lines[i + 1].strip() == '':
                i += 1
            # Collect caption lines (italic lines starting with *Figure)
            caption_lines = []
            while i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith('*Figure') or (caption_lines and next_line and not next_line.startswith('**') and not next_line.startswith('Insert')):
                    caption_lines.append(next_line)
                    i += 1
                    # Stop if this line ends with *
                    if next_line.endswith('*'):
                        break
                else:
                    break

            # Clean caption: remove surrounding asterisks and leading "Figure X -" prefix
            # (LaTeX will add its own "Figure X:" numbering)
            caption = ' '.join(caption_lines)
            caption = re.sub(r'^\*+\s*', '', caption)
            caption = re.sub(r'\s*\*+$', '', caption)
            caption = re.sub(r'^Figure\s+\d+\s*[-\.]\s*', '', caption)
            # Remove any remaining stray asterisks (from docx italic spans)
            caption = caption.replace(',* *', ', ').replace('* *', ' ')
            if not caption:
                caption = f"Figure {fig_num}"

            output_lines.append(f'![{caption}]({img_path}){{ width=100% }}')
            output_lines.append('')
            i += 1
            continue

    # Match "Insert Video X here" - skip placeholder and its multi-line caption
    vid_match = re.match(r'^Insert Video \d+ here\.?$', line.strip())
    if vid_match:
        # Skip blank line after placeholder
        if i + 1 < len(lines) and lines[i + 1].strip() == '':
            i += 1
        # Skip all caption lines until we hit a blank line or a new section
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line == '':
                i += 1
                break
            i += 1
        i += 1
        continue

    # Also catch stray "Insert Video" or "*Insert Video*" lines
    if re.match(r'^\*?Insert Video', line.strip()):
        # Skip this line and following caption lines
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line == '':
                i += 1
                break
            i += 1
        i += 1
        continue

    output_lines.append(line)
    i += 1

final_md = '\n'.join(output_lines)

# Remove any remaining stray video caption fragments
# These are lines that start with a quote and end with (Participant X, ..., pre/post-reveal).*
final_md = re.sub(
    r'\n["\u201c].*?\(Participant \d+,.*?(?:pre-reveal|post-reveal|reflection)\)\*?\.?\*?\s*\n',
    '\n',
    final_md,
    flags=re.DOTALL
)

# Clean up multiple consecutive blank lines
final_md = re.sub(r'\n{3,}', '\n\n', final_md)

# Add YAML frontmatter for pandoc
title = "Evaluating Media Equality in Generative Audiovisual Composition Using Modality Constraint and Replay-Based Reveal"
author = "Thomas Didiot-Cook"

frontmatter = f"""---
title: "{title}"
author: "{author}"
geometry: margin=2.5cm
fontsize: 11pt
linestretch: 1.15
linkcolor: blue
urlcolor: blue
header-includes:
  - \\usepackage{{float}}
  - \\let\\origfigure\\figure
  - \\let\\endorigfigure\\endfigure
  - \\renewenvironment{{figure}}[1][H]{{\\origfigure[H]}}{{\\endorigfigure}}
---

"""

final_md = frontmatter + final_md

# Write the clean markdown
output_md = BASE / "OS_Didiot_inline.md"
output_md.write_text(final_md)
print(f"Written: {output_md}")

# Convert to PDF
output_pdf = BASE / "OS_Didiot_inline.pdf"
cmd = [
    "pandoc",
    str(output_md),
    "-o", str(output_pdf),
    "--pdf-engine=tectonic",
    "--standalone",
]

print(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode == 0:
    print(f"PDF created: {output_pdf}")
else:
    print(f"Error:\n{result.stderr}")
