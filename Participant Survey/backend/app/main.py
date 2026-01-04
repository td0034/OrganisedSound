import os
import csv
import io
import json
import re
from pathlib import Path
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import Base, engine, get_db
from .models import Participant, ResponseSection, ParticipantAddendum
from .schemas import SaveSectionRequest, SaveAddendumRequest, SkipAddendumRequest

APP_TITLE = os.environ.get("APP_TITLE", "Participant Survey")
PARTICIPANT_ID_RE = re.compile(r"^\d{4}[A-Za-z]$")
EXPORTS_PATH = Path(os.environ["EXPORTS_DIR"]).resolve() if os.environ.get("EXPORTS_DIR") else None

def write_export(filename: str, content: str) -> None:
    if EXPORTS_PATH is None:
        return
    EXPORTS_PATH.mkdir(parents=True, exist_ok=True)
    (EXPORTS_PATH / filename).write_text(content, encoding="utf-8")

def build_sections_payload(db: Session):
    rows = db.execute(select(ResponseSection)).scalars().all()
    return [
        {
            "participant_id": r.participant_id,
            "section_key": r.section_key,
            "payload": r.payload,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None
        }
        for r in rows
    ]

def build_addendum_payload(db: Session):
    rows = db.execute(select(ParticipantAddendum)).scalars().all()
    return [
        {
            "session_id": r.session_id,
            "participant_code": r.participant_code,
            "skipped": r.skipped,
            "piece_title_favourite": r.piece_title_favourite,
            "piece_description_one_line": r.piece_description_one_line,
            "authorship_attribution": r.authorship_attribution,
            "authorship_reason": r.authorship_reason,
            "return_likelihood": r.return_likelihood,
            "return_conditions": r.return_conditions,
            "context_of_use": r.context_of_use,
            "context_other": r.context_other,
            "target_user": r.target_user,
            "target_user_other": r.target_user_other,
            "remove_one_thing": r.remove_one_thing,
            "add_one_thing": r.add_one_thing,
            "collaboration_expectation": r.collaboration_expectation,
            "collaboration_reason": r.collaboration_reason,
            "confidence_recreate_tomorrow": r.confidence_recreate_tomorrow,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None
        }
        for r in rows
    ]

def build_sections_csv(payload):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["participant_id", "section_key", "payload_json", "updated_at"])
    for r in payload:
        w.writerow([
            r["participant_id"],
            r["section_key"],
            (r["payload"] if r["payload"] is not None else {}),
            r["updated_at"] or ""
        ])
    buf.seek(0)
    return buf.getvalue()

def build_addendum_csv(payload):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "session_id",
        "participant_code",
        "skipped",
        "piece_title_favourite",
        "piece_description_one_line",
        "authorship_attribution",
        "authorship_reason",
        "return_likelihood",
        "return_conditions",
        "context_of_use",
        "context_other",
        "target_user",
        "target_user_other",
        "remove_one_thing",
        "add_one_thing",
        "collaboration_expectation",
        "collaboration_reason",
        "confidence_recreate_tomorrow",
        "created_at",
        "updated_at"
    ])
    for r in payload:
        context_value = r["context_of_use"]
        w.writerow([
            r["session_id"],
            r["participant_code"],
            r["skipped"],
            r["piece_title_favourite"] or "",
            r["piece_description_one_line"] or "",
            r["authorship_attribution"] or "",
            r["authorship_reason"] or "",
            r["return_likelihood"] if r["return_likelihood"] is not None else "",
            r["return_conditions"] or "",
            json.dumps(context_value) if context_value is not None else "",
            r["context_other"] or "",
            r["target_user"] or "",
            r["target_user_other"] or "",
            r["remove_one_thing"] or "",
            r["add_one_thing"] or "",
            r["collaboration_expectation"] or "",
            r["collaboration_reason"] or "",
            r["confidence_recreate_tomorrow"] if r["confidence_recreate_tomorrow"] is not None else "",
            r["created_at"] or "",
            r["updated_at"] or ""
        ])
    buf.seek(0)
    return buf.getvalue()

def update_exports(db: Session) -> None:
    if EXPORTS_PATH is None:
        return
    payload = build_sections_payload(db)
    write_export("sections.json", json.dumps(payload, indent=2))
    write_export("sections.csv", build_sections_csv(payload))
    addendum_payload = build_addendum_payload(db)
    write_export("participant_addendum.json", json.dumps(addendum_payload, indent=2))
    write_export("participant_addendum.csv", build_addendum_csv(addendum_payload))

app = FastAPI(title=APP_TITLE)

# Create tables on startup (simple, migration-free)
Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "app_title": APP_TITLE})

@app.post("/api/save_section")
def save_section(req: SaveSectionRequest, db: Session = Depends(get_db)):
    # Ensure participant exists
    participant = db.get(Participant, req.participant_id)
    if participant is None:
        participant = Participant(participant_id=req.participant_id, session_meta={})
        db.add(participant)
        db.flush()

    # If this is meta, merge into participant.session_meta
    if req.section_key == "meta":
        meta = dict(participant.session_meta or {})
        meta.update(req.payload or {})
        participant_id = (req.participant_id or meta.get("participant_id") or "").strip()
        if not PARTICIPANT_ID_RE.match(participant_id):
            raise HTTPException(
                status_code=400,
                detail="Invalid participant ID. Use 4 digits + 1 letter."
            )
        participant.session_meta = meta

    # Upsert section
    existing = db.execute(
        select(ResponseSection).where(
            ResponseSection.participant_id == req.participant_id,
            ResponseSection.section_key == req.section_key
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = ResponseSection(
            participant_id=req.participant_id,
            section_key=req.section_key,
            payload=req.payload
        )
        db.add(existing)
    else:
        existing.payload = req.payload

    db.commit()
    update_exports(db)
    return {"ok": True, "participant_id": req.participant_id, "section_key": req.section_key}

@app.post("/api/addendum/save")
def save_addendum(req: SaveAddendumRequest, db: Session = Depends(get_db)):
    participant = db.get(Participant, req.participant_code)
    if participant is None:
        participant = Participant(participant_id=req.participant_code, session_meta={})
        db.add(participant)
        db.flush()

    existing = db.execute(
        select(ParticipantAddendum).where(
            ParticipantAddendum.session_id == req.session_id,
            ParticipantAddendum.participant_code == req.participant_code
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = ParticipantAddendum(
            session_id=req.session_id,
            participant_code=req.participant_code
        )
        db.add(existing)

    if req.skipped:
        existing.skipped = True
        existing.piece_title_favourite = None
        existing.piece_description_one_line = None
        existing.authorship_attribution = None
        existing.authorship_reason = None
        existing.return_likelihood = None
        existing.return_conditions = None
        existing.context_of_use = None
        existing.context_other = None
        existing.target_user = None
        existing.target_user_other = None
        existing.remove_one_thing = None
        existing.add_one_thing = None
        existing.collaboration_expectation = None
        existing.collaboration_reason = None
        existing.confidence_recreate_tomorrow = None
    else:
        existing.skipped = False
        existing.piece_title_favourite = req.piece_title_favourite
        existing.piece_description_one_line = req.piece_description_one_line
        existing.authorship_attribution = req.authorship_attribution
        existing.authorship_reason = req.authorship_reason
        existing.return_likelihood = req.return_likelihood
        existing.return_conditions = req.return_conditions
        existing.context_of_use = req.context_of_use
        existing.context_other = req.context_other
        existing.target_user = req.target_user
        existing.target_user_other = req.target_user_other
        existing.remove_one_thing = req.remove_one_thing
        existing.add_one_thing = req.add_one_thing
        existing.collaboration_expectation = req.collaboration_expectation
        existing.collaboration_reason = req.collaboration_reason
        existing.confidence_recreate_tomorrow = req.confidence_recreate_tomorrow

    db.commit()
    update_exports(db)
    return {"ok": True, "participant_code": req.participant_code, "session_id": req.session_id}

@app.post("/api/addendum/skip")
def skip_addendum(req: SkipAddendumRequest, db: Session = Depends(get_db)):
    participant = db.get(Participant, req.participant_code)
    if participant is None:
        participant = Participant(participant_id=req.participant_code, session_meta={})
        db.add(participant)
        db.flush()

    existing = db.execute(
        select(ParticipantAddendum).where(
            ParticipantAddendum.session_id == req.session_id,
            ParticipantAddendum.participant_code == req.participant_code
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = ParticipantAddendum(
            session_id=req.session_id,
            participant_code=req.participant_code
        )
        db.add(existing)

    existing.skipped = True
    existing.piece_title_favourite = None
    existing.piece_description_one_line = None
    existing.authorship_attribution = None
    existing.authorship_reason = None
    existing.return_likelihood = None
    existing.return_conditions = None
    existing.context_of_use = None
    existing.context_other = None
    existing.target_user = None
    existing.target_user_other = None
    existing.remove_one_thing = None
    existing.add_one_thing = None
    existing.collaboration_expectation = None
    existing.collaboration_reason = None
    existing.confidence_recreate_tomorrow = None

    db.commit()
    update_exports(db)
    return {"ok": True, "participant_code": req.participant_code, "session_id": req.session_id}

@app.get("/api/load/{participant_id}")
def load_participant(participant_id: str, db: Session = Depends(get_db)):
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found")

    sections = db.execute(
        select(ResponseSection).where(ResponseSection.participant_id == participant_id)
    ).scalars().all()

    return {
        "participant_id": participant.participant_id,
        "session_meta": participant.session_meta or {},
        "sections": {s.section_key: s.payload for s in sections}
    }

@app.get("/api/export/sections.json")
def export_sections_json(db: Session = Depends(get_db)):
    payload = build_sections_payload(db)
    write_export("sections.json", json.dumps(payload, indent=2))
    return payload

@app.get("/api/export/sections.csv")
def export_sections_csv(db: Session = Depends(get_db)):
    payload = build_sections_payload(db)
    csv_text = build_sections_csv(payload)
    write_export("sections.csv", csv_text)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sections.csv"'}
    )

@app.get("/api/export/participant_addendum.json")
def export_addendum_json(db: Session = Depends(get_db)):
    payload = build_addendum_payload(db)
    write_export("participant_addendum.json", json.dumps(payload, indent=2))
    return payload

@app.get("/api/export/participant_addendum.csv")
def export_addendum_csv(db: Session = Depends(get_db)):
    payload = build_addendum_payload(db)
    csv_text = build_addendum_csv(payload)
    write_export("participant_addendum.csv", csv_text)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="participant_addendum.csv"'}
    )
