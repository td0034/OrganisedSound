# Audiovisual Intermediality — Participant Survey Capture (Docker)

## Purpose
This repository provides a small, self-hosted web application for capturing **participant questionnaire data during in-person sessions**.

The study uses a multi-block protocol:
- Session meta (participant ID, counterbalanced block order)
- Session type selection (solo or dyad-only)
- Background questions
- Three blocks (A/B/C), each split into:
  - Part A: pre-reveal (immediately after capture)
  - Part B: post-reveal (after replay with sound+light)
- End-of-session comparison
- Optional dyad questionnaire (if participant took part)
- Final reflections (optional addendum)

Dyad-only sessions skip the solo blocks and the end-of-session comparison and go straight to the dyad questionnaire and final reflections.

A key requirement is that participants can **save after each major section** to avoid data loss and to support a structured session flow.

## Design goals
- Simple, robust local deployment via Docker Compose.
- Data stored in a database in a format that is easy to analyse and graph later.
- Minimal UI suitable for a darkened room (dark theme).
- “Wizard” style flow so the researcher can step participants through blocks in the correct order.

## Architecture
- `db`: PostgreSQL 16
- `web`: FastAPI (Python) serving:
  - A single-page wizard UI (`/`)
  - API endpoints for saving/loading sections and exporting data

### Data model (Postgres)
- `participants`
  - `participant_id` (primary key)
  - `session_meta` (JSONB)
- `response_sections`
  - unique `(participant_id, section_key)`
  - `payload` (JSONB)
  - timestamps
- `participant_addendum`
  - unique `(session_id, participant_code)`
  - structured reflection fields (final reflections page)
  - timestamps

Each major page/section is stored as one JSON document. This makes the dataset easy to load into Python/pandas later:
- groupby participant_id
- compare sections/conditions
- flatten JSON as required for plotting

## Running locally
1. Install Docker + Docker Compose.
2. From repo root:
   ```bash
   docker compose up --build
   ```

## Exports
On every successful save, the app writes fresh export files to:
- `exports/sections.csv`
- `exports/sections.json`
- `exports/participant_addendum.csv`
- `exports/participant_addendum.json`
