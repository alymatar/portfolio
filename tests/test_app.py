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
