import os, io, csv, hashlib, asyncio, random
from pathlib import Path
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy import select

from .db import Base, engine, SessionLocal, get_db
from .models import Clip, Session, Rating, SessionEnd
from .schemas import CreateSessionRequest, SaveRatingRequest, SaveSessionEndRequest
from .range_utils import range_file_response

APP_TITLE = os.environ.get("APP_TITLE", "Clip Ratings")
CLIPS_DIR = Path(os.environ.get("CLIPS_DIR", "")).resolve()
SCAN_SECONDS = int(os.environ.get("CLIPS_SCAN_SECONDS", "20"))
TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "dev_only_change_me")

VIDEO_EXTS = {".mp4", ".m4v", ".mov"}

app = FastAPI(title=APP_TITLE)
Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _make_token() -> str:
    raw = hashlib.sha256(f"{TOKEN_SECRET}-{os.urandom(16).hex()}".encode()).hexdigest()
    return raw[:32]

async def scan_clips_forever():
    if not CLIPS_DIR.exists():
        return
    while True:
        try:
            files = [p for p in CLIPS_DIR.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
            files.sort(key=lambda p: p.name.lower())

            for fp in files:
                sha = _sha256_file(fp)
                size = fp.stat().st_size

                with SessionLocal() as db:
                    existing = db.execute(select(Clip).where(Clip.filename == fp.name)).scalar_one_or_none()
                    if existing is None:
                        db.add(Clip(filename=fp.name, sha256=sha, filesize=size))
                        db.commit()
                    else:
                        if existing.sha256 != sha or existing.filesize != size:
                            existing.sha256 = sha
                            existing.filesize = size
                            db.commit()
        except Exception:
            pass

        await asyncio.sleep(SCAN_SECONDS)

@app.on_event("startup")
async def _startup():
    asyncio.create_task(scan_clips_forever())

@app.get("/health")
def health():
    return {"ok": True, "clips_dir": str(CLIPS_DIR)}

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "app_title": APP_TITLE})

@app.get("/s/{token}", response_class=HTMLResponse)
def session_root(token: str, request: Request):
    return templates.TemplateResponse("session.html", {"request": request, "app_title": APP_TITLE, "token": token})

@app.get("/s/{token}/clip/{clip_id}", response_class=HTMLResponse)
def session_clip(token: str, clip_id: int, request: Request):
    return templates.TemplateResponse("session.html", {"request": request, "app_title": APP_TITLE, "token": token, "clip_id": clip_id})

@app.get("/media/{clip_id}")
def media(clip_id: int, request: Request, db: OrmSession = Depends(get_db)):
    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    path = (CLIPS_DIR / clip.filename).resolve()
    if not path.exists() or CLIPS_DIR not in path.parents:
        raise HTTPException(status_code=404, detail="File missing")
    return range_file_response(request, path)

@app.post("/api/session/create")
def create_session(req: CreateSessionRequest, db: OrmSession = Depends(get_db)):
    clips = db.execute(select(Clip)).scalars().all()
    if not clips:
        raise HTTPException(status_code=400, detail="No clips found. Add files to CLIPS_DIR and wait for scan.")
    clip_ids = [c.clip_id for c in clips]
    random.shuffle(clip_ids)

    token = _make_token()
    s = Session(token=token, rater_label=req.rater_label or "", playlist={"clip_ids": clip_ids})
    db.add(s)
    db.commit()

    return {"token": token, "share_url": f"/s/{token}", "total": len(clip_ids)}

@app.get("/api/session/{token}/state")
def session_state(token: str, db: OrmSession = Depends(get_db)):
    s = db.get(Session, token)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")

    clip_ids = (s.playlist or {}).get("clip_ids", [])
    ratings = db.execute(select(Rating).where(Rating.token == token)).scalars().all()
    done_ids = sorted({r.clip_id for r in ratings})

    return {
        "token": token,
        "label": s.rater_label,
        "clip_ids": clip_ids,
        "done_ids": done_ids,
        "total": len(clip_ids)
    }

@app.get("/api/session/{token}/clip/{clip_id}")
def clip_info(token: str, clip_id: int, db: OrmSession = Depends(get_db)):
    s = db.get(Session, token)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")

    clip = db.get(Clip, clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")

    existing = db.execute(select(Rating).where(Rating.token == token, Rating.clip_id == clip_id)).scalar_one_or_none()

    return {
        "clip": {"clip_id": clip.clip_id, "filename": clip.filename, "filesize": clip.filesize},
        "existing": (existing.payload if existing else None),
        "existing_meta": ({
            "watched_complete": existing.watched_complete,
            "watch_progress_sec": existing.watch_progress_sec,
            "duration_sec": existing.duration_sec
        } if existing else None)
    }

@app.post("/api/rating/save")
def save_rating(req: SaveRatingRequest, db: OrmSession = Depends(get_db)):
    s = db.get(Session, req.token)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # upsert
    existing = db.execute(
        select(Rating).where(Rating.token == req.token, Rating.clip_id == req.clip_id)
    ).scalar_one_or_none()

    if existing is None:
        existing = Rating(
            token=req.token,
            clip_id=req.clip_id,
            watched_complete=req.watched_complete,
            watch_progress_sec=req.watch_progress_sec,
            duration_sec=req.duration_sec,
            payload=req.payload
        )
        db.add(existing)
    else:
        existing.watched_complete = req.watched_complete
        existing.watch_progress_sec = req.watch_progress_sec
        existing.duration_sec = req.duration_sec
        existing.payload = req.payload

    db.commit()
    return {"ok": True}

@app.post("/api/session/end")
def save_session_end(req: SaveSessionEndRequest, db: OrmSession = Depends(get_db)):
    s = db.get(Session, req.token)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")

    existing = db.get(SessionEnd, req.token)
    if existing is None:
        db.add(SessionEnd(token=req.token, payload=req.payload))
    else:
        existing.payload = req.payload
    db.commit()
    return {"ok": True}

@app.get("/api/export/ratings.csv")
def export_ratings_csv(db: OrmSession = Depends(get_db)):
    rows = db.execute(select(Rating)).scalars().all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["token", "clip_id", "watched_complete", "watch_progress_sec", "duration_sec", "payload_json", "updated_at"])
    for r in rows:
        w.writerow([
            r.token,
            r.clip_id,
            r.watched_complete,
            r.watch_progress_sec,
            r.duration_sec,
            (r.payload or {}),
            r.updated_at.isoformat() if r.updated_at else ""
        ])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="ratings.csv"'})
