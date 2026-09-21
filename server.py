from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import re
import pathlib
import urllib.parse
import requests

APP_NAME = "sach_n_jngd_music"
ROOT = pathlib.Path(__file__).resolve().parent

app = FastAPI(title=APP_NAME, version="1.0.0")


TIMEOUT = (10, 30)
UA = f"{APP_NAME}/1.0 (music discovery app)"

def get_json(url, params=None, timeout=TIMEOUT):
    r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": UA})
    r.raise_for_status()
    return r.json()

def safe_text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    return str(value)

def archive_search(q):
    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": f'(title:({q}) OR creator:({q}) OR description:({q})) AND mediatype:audio',
        "fl[]": [
            "identifier,title,creator,year,description,license,rights,mediatype"
        ],
        "rows": 20,
        "page": 1,
        "output": "json",
    }
    data = get_json(url, params)
    out = []
    for d in data.get("response", {}).get("docs", []):
        ident = safe_text(d.get("identifier")).strip()
        if not ident:
            continue
        rights = safe_text(d.get("rights")).strip()
        license_name = safe_text(d.get("license")).strip()
        # We show source items even when rights metadata is missing,
        # but only enable direct download after metadata/file checks.
        out.append({
            "source": "Internet Archive",
            "title": safe_text(d.get("title")) or ident,
            "artist": safe_text(d.get("creator")),
            "year": safe_text(d.get("year")),
            "id": ident,
            "license": license_name or rights,
            "download": f"/api/download/archive?id={urllib.parse.quote(ident, safe='')}",
            "source_url": f"https://archive.org/details/{urllib.parse.quote(ident, safe='')}",
            "download_label": "Check MP3 / Download",
        })
    return out

def audius_search(q):
    url = "https://api.audius.co/v1/tracks/search"
    data = get_json(url, {"query": q, "limit": 20})
    out = []
    for d in data.get("data", []):
        tid = safe_text(d.get("id")).strip()
        user = d.get("user") or {}
        if not tid:
            continue
        handle = safe_text(user.get("handle"))
        permalink = safe_text(d.get("permalink"))
        source_url = (
            f"https://audius.co/{urllib.parse.quote(handle, safe='')}/"
            f"{urllib.parse.quote(permalink, safe='')}"
            if handle and permalink else "https://audius.co/"
        )
        out.append({
            "source": "Audius",
            "title": safe_text(d.get("title")),
            "artist": safe_text(user.get("name")),
            "year": "",
            "id": tid,
            "license": "",
            "download": f"/api/download/audius?id={urllib.parse.quote(tid, safe='')}",
            "source_url": source_url,
            "download_label": "Open / Stream",
        })
    return out

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/health")
def health():
    return {"ok": True, "app": APP_NAME}

@app.get("/api/search")
def search(q: str = Query(..., min_length=1, max_length=200)):
    q = q.strip()
    if not q:
        return JSONResponse({"results": [], "errors": []})

    results = []
    errors = []

    for name, fn in (
        ("Internet Archive", archive_search),
        ("Audius", audius_search),
    ):
        try:
            results.extend(fn(q))
        except Exception as exc:
            errors.append(f"{name}: temporarily unavailable")

    # Keep the first 60 results, preserving provider grouping/order.
    return {"results": results[:60], "errors": errors}

@app.get("/api/download/archive")
def download_archive(id: str = Query(..., min_length=1)):
    meta = get_json(
        f"https://archive.org/metadata/{urllib.parse.quote(id, safe='')}"
    )
    metadata = meta.get("metadata") or {}
    files = meta.get("files") or []

    # Require some rights/licensing metadata before enabling a direct file.
    rights = safe_text(metadata.get("rights")).strip()
    license_name = safe_text(metadata.get("license")).strip()
    if not (rights or license_name):
        return JSONResponse(
            {"error": "This item does not expose clear rights/license metadata; open the source page to review it."},
            status_code=403,
        )

    candidates = []
    for f in files:
        name = safe_text(f.get("name"))
        if not re.search(r"\.(mp3|flac|ogg|wav|m4a)$", name, re.I):
            continue
        if f.get("private"):
            continue
        if f.get("source") == "original" or not f.get("source"):
            candidates.append(f)

    if not candidates:
        return JSONResponse(
            {"error": "No downloadable audio file was exposed by this item."},
            status_code=404,
        )

    candidates.sort(key=lambda f: (
        not safe_text(f.get("name")).lower().endswith(".mp3"),
        len(safe_text(f.get("name"))),
    ))
    name = safe_text(candidates[0].get("name"))
    file_url = (
        "https://archive.org/download/"
        + urllib.parse.quote(id, safe="")
        + "/"
        + urllib.parse.quote(name, safe="")
    )
    return RedirectResponse(file_url, status_code=302)


@app.get("/api/download/audius")
def download_audius(id: str = Query(..., min_length=1)):
    # Audius exposes a stream endpoint; this opens the provider stream and does
    # not bypass DRM or turn protected media into an MP3.
    url = f"https://api.audius.co/v1/tracks/{urllib.parse.quote(id, safe='')}/stream"
    try:
        r = requests.get(url, timeout=TIMEOUT, allow_redirects=False, headers={"User-Agent": UA})
        location = r.headers.get("location")
        if location:
            return RedirectResponse(location, status_code=302)
    except requests.RequestException:
        pass
    return JSONResponse(
        {"error": "Audius stream is not currently available. Open the source page instead."},
        status_code=404,
    )

# Kept for future static assets; the app page itself is served by /.
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
