# Standalone External Rater Survey (Docker)

## What this app does
This is a standalone web application for collecting blinded ratings of short audiovisual clips.

Key behaviours:
- The app scans a mounted `trimmed_clips/` folder for video files and builds a clip index.
- A researcher creates a tokenised rater session (randomised playlist).
- Each clip is presented on its own page.
- The rating form is hidden until the rater watches the clip to the end at least once.
- Raters can replay clips freely.
- Ratings are stored in Postgres (JSONB) and exported as CSV for analysis.
- Per-clip ratings include memorability, perceived agency, and best-context selection.

## Quick start
1. Put video clips in `./trimmed_clips/` (e.g., `.mp4`, `.m4v`, `.mov`).
2. From this folder:
   ```bash
   docker compose up --build
   ```

## Exports
On every successful rating save, the app writes:
- `exports/ratings.csv`
  - includes `memorability`, `perceived_agency`, and `best_context`

## Clip manifest
Maintain `trimmed_clips/manifest.csv` with one row per clip, including at least:
- `clip_id`
- `participant_code`
- `condition`
- `filepath`
