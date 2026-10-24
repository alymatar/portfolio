from html import escape

from fastapi.testclient import TestClient

from app.content import load_content
from app.main import app

client = TestClient(app)


def test_home_page_renders():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    content = load_content()
    assert content.profile.name in html
    assert content.profile.headline in html
    for section in ("about", "skills", "projects", "experience", "education", "contact"):
        assert f'id="{section}"' in html


def test_home_page_shows_every_project():
    html = client.get("/").text
    for project in load_content().projects:
        assert escape(project.title, quote=False) in html


def test_static_assets_are_served():
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/theme.js").status_code == 200
    assert client.get("/static/favicon.svg").status_code == 200


def test_photo_is_served():
    for path in ("/static/img/aly-matar.webp", "/static/img/aly-matar.jpg"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/")


def test_cv_download():
    cv = load_content().cv
    html = client.get("/").text
    assert f'download="{cv.download_name}"' in html
    response = client.get(f"/static/{cv.file}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_projects_api_lists_projects():
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert isinstance(projects, list)
    assert len(projects) == len(load_content().projects)
    first = projects[0]
    for key in ("slug", "title", "summary", "tags", "status"):
        assert key in first


def test_single_project_api():
    slug = load_content().projects[0].slug
    response = client.get(f"/api/projects/{slug}")
    assert response.status_code == 200
    assert response.json()["slug"] == slug


def test_unknown_project_returns_json_404():
    response = client.get("/api/projects/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_unknown_page_returns_html_404():
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert "Page not found" in response.text


def test_no_phone_number_on_site():
    html = client.get("/").text
    assert "+20" not in html
    assert "533 2919" not in html


def test_graduation_photo_is_served_and_shown():
    for path in ("/static/img/aly-graduation.webp", "/static/img/aly-graduation.jpg"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/")
    html = client.get("/").text
    assert "img/aly-graduation.jpg" in html
    assert 'alt="Aly receiving his BSc diploma, Bauman MSTU Kaluga Branch"' in html


def test_link_preview_tags_use_the_live_url():
    html = client.get("/").text
    site = load_content().site
    assert site.page_url == "https://alymatar.github.io/"
    assert f'<meta property="og:title" content="{escape(site.title)}">' in html
    assert '<meta property="og:url" content="https://alymatar.github.io/">' in html
    assert '<link rel="canonical" href="https://alymatar.github.io/">' in html
    assert '<meta property="og:image" content="https://alymatar.github.io/static/img/aly-matar.jpg">' in html


def test_preview_image_path_relative_to_static():
    from app.content import Site

    site = Site(title="t", description="d", url="https://example.org", image="img/a.jpg")
    assert site.page_url == "https://example.org/"
    assert site.image_url == "https://example.org/static/img/a.jpg"


def test_api_answers_at_the_json_paths_too():
    """The page links to the .json paths, which is where the static site has its API."""
    assert client.get("/api/health.json").json() == client.get("/api/health").json()
    assert client.get("/api/projects.json").json() == client.get("/api/projects").json()
    slug = load_content().projects[0].slug
    response = client.get(f"/api/projects/{slug}.json")
    assert response.status_code == 200
    assert response.json()["slug"] == slug
    assert client.get("/api/projects/does-not-exist.json").status_code == 404
    html = client.get("/").text
    assert 'href="/api/projects.json"' in html
    assert 'href="/api/docs/"' in html


def test_no_coming_soon_card():
    html = client.get("/").text
    assert "coming soon" not in html.lower()
    projects = load_content().projects
    assert len(projects) == 4
    assert all(p.status in ("public", "private") for p in projects)


def test_no_tab_bot_address_anywhere():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    skip = {".git", ".venv", "venv", "dist", "__pycache__", ".pytest_cache"}
    needle = "tab" + ".bot"
    for path in root.rglob("*"):
        if path.is_file() and not skip.intersection(path.relative_to(root).parts):
            if path.suffix in {".py", ".html", ".css", ".js", ".yaml", ".yml", ".md", ".txt", ".toml", ".ini"}:
                assert needle not in path.read_text(encoding="utf-8", errors="ignore"), path


def test_static_export_for_github_pages(tmp_path):
    import json

    from scripts.export_static import export

    out = export(tmp_path / "site")
    for name in ("index.html", "404.html", ".nojekyll", "favicon.svg", "static/Aly_Matar_CV.pdf",
                 "static/img/aly-matar.jpg", "static/img/aly-graduation.jpg",
                 "api/health.json", "api/projects.json", "api/openapi.json", "api/docs/index.html"):
        assert (out / name).is_file(), name
    assert (out / ".nojekyll").read_bytes() == b""
    assert not (out / "_worker.js").exists()
    assert not (out / "tab-site.json").exists()

    index = (out / "index.html").read_text(encoding="utf-8")
    assert "http://testserver" not in index
    assert 'href="/static/Aly_Matar_CV.pdf"' in index
    assert 'href="/api/projects.json"' in index
    assert "Page not found" in (out / "404.html").read_text(encoding="utf-8")

    assert json.loads((out / "api/health.json").read_text(encoding="utf-8"))["status"] == "ok"
    projects = json.loads((out / "api/projects.json").read_text(encoding="utf-8"))
    assert len(projects) == 4
    for project in projects:
        single = json.loads((out / "api/projects" / f"{project['slug']}.json").read_text(encoding="utf-8"))
        assert single == project

    openapi = json.loads((out / "api/openapi.json").read_text(encoding="utf-8"))
    assert set(openapi["paths"]) == {"/api/health.json", "/api/projects.json", "/api/projects/{slug}.json"}
