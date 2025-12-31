import re
import mimetypes
from pathlib import Path
from fastapi import Request
from fastapi.responses import StreamingResponse, FileResponse

_CHUNK = 1024 * 1024

def range_file_response(request: Request, path: Path):
    ctype, _ = mimetypes.guess_type(str(path))
    media_type = ctype or "application/octet-stream"
    size = path.stat().st_size

    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(path, media_type=media_type, headers={"Accept-Ranges":"bytes"})

    m = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not m:
        return FileResponse(path, media_type=media_type, headers={"Accept-Ranges":"bytes"})

    start_s, end_s = m.group(1), m.group(2)

    if start_s == "" and end_s == "":
        return FileResponse(path, media_type=media_type, headers={"Accept-Ranges":"bytes"})

    if start_s == "":
        # suffix range: last N bytes
        length = int(end_s)
        start = max(size - length, 0)
        end = size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else size - 1

    start = max(0, min(start, size - 1))
    end = max(start, min(end, size - 1))
    length = end - start + 1

    def iterfile():
        with path.open("rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(_CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    return StreamingResponse(iterfile(), status_code=206, headers=headers, media_type=media_type)
