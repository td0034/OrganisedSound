import os
import csv
import io
from fastapi import FastAPI, Depends, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import Base, engine, get_db
from .models import Participant, ResponseSection
from .schemas import SaveSectionRequest

APP_TITLE = os.environ.get("APP_TITLE", "Participant Survey")

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
    return {"ok": True, "participant_id": req.participant_id, "section_key": req.section_key}

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

@app.get("/api/export/sections.csv")
def export_sections_csv(db: Session = Depends(get_db)):
    rows = db.execute(select(ResponseSection)).scalars().all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["participant_id", "section_key", "payload_json", "updated_at"])

    for r in rows:
        w.writerow([
            r.participant_id,
            r.section_key,
            (r.payload if r.payload is not None else {}),
            r.updated_at.isoformat() if r.updated_at else ""
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sections.csv"'}
    )
