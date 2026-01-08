# Organised Sound Surveys

This repo contains two Dockerized surveys and a results pipeline:
- `Participant Survey/` for in-person participant questionnaires.
- `Rater Survey/` for blinded external clip ratings.
- `Paper/Results/` for reproducible tables/figures from survey exports + clip manifest.

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
See `Paper/Results/README.md` for environment setup and the reproducible results generator.
