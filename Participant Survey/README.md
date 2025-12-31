# Audiovisual Intermediality — Participant Survey Capture (Docker)

## Purpose
This repository provides a small, self-hosted web application for capturing **participant questionnaire data during in-person sessions**.

The study uses a multi-block protocol:
- Session meta (participant ID, counterbalanced block order)
- Background questions
- Three blocks (A/B/C), each split into:
  - Part A: pre-reveal (immediately after capture)
  - Part B: post-reveal (after replay with sound+light)
- End-of-session comparison
- Optional dyad questionnaire (if participant took part)

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

Each major page/section is stored as one JSON document. This makes the dataset easy to load into Python/pandas later:
- groupby participant_id
- compare sections/conditions
- flatten JSON as required for plotting

## Running locally
1. Install Docker + Docker Compose.
2. From repo root:
   ```bash
   docker compose up --build



## TODO (planned improvements)
- Admin panel:
  - List participants and completion status (which sections saved, last updated timestamp).
  - Quick open/resume for a participant ID.
  - Flag incomplete sessions and show missing sections.
  - One-click export buttons and (optionally) per-participant export.

- Participant access code:
  - Prompt participant to enter an “access code” of the last 4 digits of their mobile number + their initial (e.g., 9746T).
  - Store the access code with session metadata for traceability (not used for identification outside the research context).
  - Add basic validation (4 digits + 1 letter).

- Navigation:
  - Add a “Return to Start” action to restart the questionnaire quickly between participants while leaving the system running.
