# Organised Sound Surveys

This repo contains two Dockerized surveys and a results pipeline:
- `Participant Survey/` for in-person participant questionnaires.
- `Rater Survey/` for blinded external clip ratings.
- `make_results.py` to generate tables/figures from the survey exports + clip manifest.

## Structure
- `Participant Survey/`
  - Web UI at `http://localhost:8081/`
  - Auto-exports on every save:
    - `Participant Survey/exports/sections.csv`
    - `Participant Survey/exports/sections.json`
    - `Participant Survey/exports/participant_addendum.csv`
    - `Participant Survey/exports/participant_addendum.json`
- `Rater Survey/`
  - Web UI at `http://localhost:18080/`
  - Auto-exports on every rating save:
    - `Rater Survey/exports/ratings.csv`
  - Clip manifest:
    - `Rater Survey/clips/manifest.csv`

## Run the surveys
Participant Survey:
```bash
cd "Participant Survey"
docker compose up --build
```

Rater Survey:
```bash
cd "Rater Survey"
docker compose up --build
```

## Results pipeline
The results script reads the exported CSVs and the manifest:
- `Participant Survey/exports/sections.csv`
- `Participant Survey/exports/participant_addendum.csv`
- `Rater Survey/exports/ratings.csv`
- `Rater Survey/clips/manifest.csv`

Make sure `manifest.csv` uses the same `clip_id` values as the rater database (these are assigned when clips are scanned).

## Python virtualenv (for `make_results.py`)
Create and activate a virtual environment from the repo root:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
python -m pip install --upgrade pip
python -m pip install pandas numpy matplotlib
```

Exit the virtual environment:
```bash
deactivate
```

Run from the repo root:
```bash
python make_results.py
```

Selective runs:
```bash
python make_results.py --participants-only
python make_results.py --raters-only
```

Override paths if needed:
```bash
python make_results.py \
  --participant-csv "Participant Survey/exports/sections.csv" \
  --rater-csv "Rater Survey/exports/ratings.csv" \
  --manifest-csv "Rater Survey/clips/manifest.csv"
```

Outputs are written to `out/` (tables, figures, results snippets).
