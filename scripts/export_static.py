"""Export the site as a static snapshot (HTML, assets and the JSON API as files).

Usage:
    python scripts/export_static.py [output_dir]     # default: dist/

The live site is this snapshot, served by a static host. It renders the
real FastAPI app with its test client, so the pages are exactly what
`uvicorn app.main:app` serves. The JSON API is written as .json files, and a
tiny `_worker.js` maps the extension-less /api/... URLs onto them.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.content import load_content  # noqa: E402
from app.main import APP_DIR, app  # noqa: E402

BASE = "http://testserver"

WORKER_JS = """// Serves the static snapshot. The JSON API is pre-rendered as .json files;
// this maps the extension-less /api/... URLs onto them, like the FastAPI app.
const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "access-control-allow-origin": "*",
  "cache-control": "public, max-age=300",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let path = url.pathname.replace(/\\/+$/, "") || "/";
    const isApi =
      path === "/api/health" ||
      path === "/api/projects" ||
      /^\\/api\\/projects\\/[a-z0-9-]+$/.test(path);
    if (isApi) {
      const asset = await env.ASSETS.fetch(new URL(path + ".json", url.origin));
      if (asset.ok) {
        return new Response(asset.body, { status: 200, headers: JSON_HEADERS });
      }
      const detail = path.startsWith("/api/projects/") ? "Project not found" : "Not Found";
      return new Response(JSON.stringify({ detail }), { status: 404, headers: JSON_HEADERS });
    }
    const response = await env.ASSETS.fetch(request);
    if (response.status !== 404) return response;
    const page = await env.ASSETS.fetch(new URL("/404.html", url.origin));
    return new Response(page.body, {
      status: 404,
      headers: { "content-type": "text/html; charset=utf-8" },
    });
  },
};
"""

DOCS_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>API docs · {name}</title>
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
  <p style="font:14px system-ui,sans-serif;margin:12px 20px">
    <a href="/">&larr; Back to the portfolio</a> &middot; This is a static snapshot of the API:
    GET requests work. <a href="{source}">Source on GitHub</a>
  </p>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({{ url: "/api/openapi.json", dom_id: "#swagger-ui" }});
  </script>
</body>
</html>
"""


def _get(client: TestClient, path: str, status: int = 200):
    response = client.get(path)
    assert response.status_code == status, f"{path}: {response.status_code}"
    return response


def _root_relative(html: str) -> str:
    return html.replace(BASE, "")


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export(out: Path) -> Path:
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    client = TestClient(app, base_url=BASE)
    content = load_content()

    # Pages
    (out / "index.html").write_text(_root_relative(_get(client, "/").text), encoding="utf-8")
    not_found = _get(client, "/this-page-does-not-exist", 404).text
    (out / "404.html").write_text(_root_relative(not_found), encoding="utf-8")

    # Static assets (CSS, JS, photos, CV, favicon)
    shutil.copytree(APP_DIR / "static", out / "static")
    shutil.copy2(APP_DIR / "static" / "favicon.svg", out / "favicon.svg")

    # JSON API as files
    api = out / "api"
    _write_json(api / "health.json", _get(client, "/api/health").json())
    _write_json(api / "projects.json", _get(client, "/api/projects").json())
    for project in content.projects:
        _write_json(api / "projects" / f"{project.slug}.json", _get(client, f"/api/projects/{project.slug}").json())
    _write_json(api / "openapi.json", _get(client, "/api/openapi.json").json())
    docs = api / "docs" / "index.html"
    docs.parent.mkdir(parents=True, exist_ok=True)
    docs.write_text(
        DOCS_HTML.format(name=content.profile.name, source=content.site.source_url or "/"),
        encoding="utf-8",
    )

    (out / "_worker.js").write_text(WORKER_JS, encoding="utf-8")
    _write_json(out / "tab-site.json", {
            "kind": "worker",
            "entry": "_worker.js",
            # The Worker handles 404s itself, so browser navigations to
            # /api/... reach it instead of the host's built-in 404 page.
            "worker": {"not_found_handling": "none", "html_handling": "auto-trailing-slash"},
        })
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist"
    print(f"Exported to {export(target)}")
