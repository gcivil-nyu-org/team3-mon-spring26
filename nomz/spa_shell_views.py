"""
Serve the built React app for normal browser navigations.

Django continues to handle /api/*, /admin/, /health/, and static/media; every other
GET path returns the SPA shell so client-side routing can take over once the bundle loads.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_GET


def _dist_root() -> Path:
    return Path(
        getattr(settings, "FRONTEND_DIST_DIR", settings.BASE_DIR / "frontend" / "dist")
    ).resolve()


def spa(request):
    """Serve the React SPA shell directly."""
    return spa_index(request)


def _index_candidates() -> list[Path]:
    out: list[Path] = []
    dist = _dist_root() / "index.html"
    out.append(dist)
    fb = getattr(settings, "NOMZ_SPA_FALLBACK_INDEX", None)
    if fb:
        out.append(Path(fb).resolve())
    return out


_EMBEDDED_INDEX = b"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Nomz</title>
</head>
<body>
  <div id="root"></div>
  <p style="font-family:system-ui,sans-serif;margin:1rem;color:#444">
    Frontend bundle not found. From the repo root run:
    <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>
    then reload (or use <code>npm run dev</code> on port 5173 with API proxy).
  </p>
</body>
</html>
"""


def _load_index_bytes() -> bytes:
    for p in _index_candidates():
        if p.is_file():
            return p.read_bytes()
    return _EMBEDDED_INDEX


@require_GET
def spa_index(request, spa_path: str | None = None, **kwargs):
    """**kwargs absorbs URL converter names (e.g. restaurant_id) from named SPA routes."""
    for p in _index_candidates():
        if p.is_file():
            response = HttpResponse(
                p.read_bytes(), content_type="text/html; charset=utf-8"
            )
            response["Cache-Control"] = "no-store, max-age=0"
            return response
    if not settings.DEBUG:
        return HttpResponse(
            "Nomz UI build missing: frontend/dist/index.html was not found on the server "
            "after deploy. Check Elastic Beanstalk logs for eb_build_frontend.sh and "
            "ensure Vite emitted frontend/dist/assets/.",
            status=503,
            content_type="text/plain; charset=utf-8",
        )
    return HttpResponse(_load_index_bytes(), content_type="text/html; charset=utf-8")


@require_GET
def spa_asset(request, asset_path: str):
    """Serve Vite output under <dist>/assets/ (hashed JS/CSS)."""
    assets_base = (_dist_root() / "assets").resolve()
    target = (assets_base / asset_path).resolve()
    try:
        target.relative_to(assets_base)
    except ValueError as exc:
        raise Http404() from exc
    if not target.is_file():
        raise Http404()
    content_type, _ = mimetypes.guess_type(str(target))
    response = FileResponse(
        target.open("rb"),
        content_type=content_type or "application/octet-stream",
    )
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response
