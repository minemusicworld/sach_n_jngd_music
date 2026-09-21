# sach_n_jngd_music

One-time deployable mobile-friendly music discovery web app.

## What it does

- Searches Internet Archive audio items.
- Searches Audius public catalog/streams.
- Shows provider/source links.
- Offers direct download only when the provider exposes a downloadable file and its rights/download conditions are clear.
- Does not bypass DRM, paywalls, protected playback, or provider restrictions.

## Exact project structure

```text
sach_n_jngd_music/
├── Dockerfile
├── README.md
├── requirements.txt
├── server.py
└── static/
    └── index.html
```

## Run locally

```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`.

## Render

Create a new Web Service from this GitHub repository.

- Runtime: Docker
- Branch: main
- Plan: Free
- No custom start command is required.


## Health check

`/health`

## Important

This software is for discovering/downloading media that the source/provider makes available for that purpose. It is not a tool for downloading arbitrary copyrighted commercial songs that are not offered for download.
