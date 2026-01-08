Results Generation

This folder contains a reproducible workflow for generating tables and figures for the
Organised Sound results section. Outputs are written into section-specific folders
under `Paper/Results/output/`.

Quick start (macOS/Linux)

1) Create and activate a virtual environment
   python3 -m venv .venv
   source .venv/bin/activate

2) Install dependencies
   python3 -m pip install -r requirements.txt

3) Run the generator
   python3 generate_results.py

From the repo root, you can also run:
   python3 Paper/Results/generate_results.py

By default, the script reads:
- `Participant Survey/exports/sections.json`
- `Participant Survey/exports/participant_addendum.json`
- `Rater Survey/exports/ratings.csv`
- `Rater Survey/clips/manifest.csv`

You can override paths and output location:
  python generate_results.py \
    --sections-json "../Participant Survey/exports/sections.json" \
    --addendum-json "../Participant Survey/exports/participant_addendum.json" \
    --rater-csv "../Rater Survey/exports/ratings.csv" \
    --manifest-csv "../Rater Survey/clips/manifest.csv" \
    --out-root "output"

Outputs

The script writes tables, figures, and captions to:
`Paper/Results/output/<section>/tables`, `Paper/Results/output/<section>/figures`, and
`Paper/Results/output/<section>/captions`.

Captions are created once and not overwritten by default. Use `--overwrite-captions`
to regenerate them.

Notes

- Figures are saved as both PNG and EPS for ease of editing.
- Word cloud output is optional and requires the `wordcloud` dependency.
- If rater data or clip manifest data are missing, the script skips those outputs and
  logs a warning.
