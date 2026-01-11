# Results_3 analysis script

This folder contains `os_results_from_json.py`, which parses the edited survey
JSON exports and generates tables, summary numbers, and EPS figures for the
paper.

## Prerequisites
- Python 3.9+ (3.10+ recommended)

## Setup (venv)
From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Deactivate when done:

```bash
deactivate
```

## Run the script
The script requires the sections JSON and optionally accepts the addendum JSON.

```bash
python os_results_from_json.py \
  --sections sections.json \
  --addendum participant_addendum.json
```

Optional output locations (defaults shown):

```bash
python os_results_from_json.py \
  --sections sections.json \
  --addendum participant_addendum.json \
  --out outputs \
  --fig outputs/figures
```

## Outputs
Running the script creates:
- `outputs/figures/core/*.eps` and `outputs/figures/core/*.png` (core figures)
- `outputs/figures/additional/*.eps` and `outputs/figures/additional/*.png` (additional figures + table plots)
- `outputs/summary_numbers.json`
- `outputs/tables/*.csv` (analysis tables)
- `outputs/log.txt` (parsing notes/warnings)

## Notes
- If you run it from the repo root, pass paths like `Paper/Results_3/sections.json`.
- Statistical tests require SciPy; if SciPy is missing, tests are skipped and noted in the outputs.
