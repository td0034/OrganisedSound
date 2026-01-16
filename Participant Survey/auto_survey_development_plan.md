# Survey Development Plan (Participant + Rater)

## Scope
- Participant Survey (in-person capture).
- Rater Survey (blinded clip ratings).
- Results pipeline (`Paper/Results/generate_results.py`) that consumes exports + manifest.

## Participant Survey
### Goals
- Capture structured in-person questionnaire data in a wizard flow.
- Save safely after each section and allow quick restart between participants.
- Ensure participant IDs are non-identifying (last 4 digits + initial).

### Data model
- `participants` table with `participant_id` (primary key) and `session_meta`.
- `response_sections` with unique `(participant_id, section_key)` and JSON payload.
- Re-saving a section updates the same row (no duplicates).

### UI flow
- Meta → Background → Block A/B/C (pre/post) → End → Dyad gate → Dyad.
- Buttons: Save & Continue, Save Only, Back, Return to Start.

### Exports
- Auto-written on every successful save:
  - `Participant Survey/exports/sections.csv`
  - `Participant Survey/exports/sections.json`
- API exports remain available for manual download.

## Rater Survey
### Goals
- Collect blinded ratings for clips with a tokenised session flow.
- Ensure ratings are only unlocked after viewing a clip to the end.

### Data model
- `clips` table generated from the `clips/` directory.
- `sessions` table with token + playlist.
- `ratings` table with unique `(token, clip_id)` and JSON payload.

### Clips & sessions
- Clips are scanned from `Rater Survey/clips/`.
- Sessions randomise clip order per token.

### Exports
- Auto-written on every successful rating save:
  - `Rater Survey/exports/ratings.csv`

### Manifest (for results)
- Maintain `Rater Survey/clips/manifest.csv` with at least:
  - `clip_id`, `participant_code`, `condition`, `filepath`
- This enables joining rater clip ratings to participant conditions.

## Results Pipeline (`Paper/Results/generate_results.py`)
### Inputs
- Participant export: `Participant Survey/exports/sections.json`
- Addendum export: `Participant Survey/exports/participant_addendum.json`
- Rater export: `Rater Survey/exports/ratings.csv`
- Manifest: `Rater Survey/clips/manifest.csv`

### Mappings (payload -> constructs)
- Participant pre: `A_1` -> preference, `A_5` -> novelty, `A_3` -> agency.
- Participant post: `B_1` -> fusion, `B_3` -> coherence, `B_4` -> constructive, `B_5` -> destructive, `B_6` -> overload.
- Dyad: `D_8` -> preference, `D_7` -> coherence, `D_6` -> fusion.
- Rater: `R_1` -> preference, `R_2` -> coherence, `R_3` -> novelty, `R_4` -> fusion,
  `R_5` -> constructive, `R_6` -> destructive, `R_7` -> overload, `R_9` -> agency.

### Outputs
- Tables and figures under `Paper/Results/output/<section>/`:
  - `tables/`, `figures/`, `captions/`.

### Usage
- Full: `python Paper/Results/generate_results.py`
- Override paths with `--sections-json`, `--addendum-json`, `--rater-csv`, `--manifest-csv`, `--out-root`.

## Non-conformances / TODO (inspect)
- Verify questionnaire→construct mappings in `Paper/Results/generate_results.py` match final wording for A/B/D/R keys.
- Confirm `manifest.csv` uses the database `clip_id` values (add a helper/export if manual sync is error-prone).
- If multiple clips per participant/condition exist, add a deterministic link (e.g., store clip_id/preset_id in participant exports and update join logic).
