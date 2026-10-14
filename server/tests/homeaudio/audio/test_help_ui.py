import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from homeaudio.audio.help_ui import HelpRoutes

@pytest.fixture
def docs_dir(tmp_path):
    (tmp_path / "index.md").write_text("# Welcome\n\n| A | B |\n| --- | --- |\n| `x` | y |\n")
    (tmp_path / "other.md").write_text("# Other page\n")
    (tmp_path / "secret.txt").write_text("nope")
    return tmp_path

@pytest.fixture
def client(docs_dir):
    app = FastAPI()
    app.include_router(HelpRoutes(docs_dir).router, prefix="/help")
    return TestClient(app)

def test_index_renders_index_md(client):
    response = client.get("/help")

    assert response.status_code == 200
    assert "<title>Welcome</title>" in response.text
    assert "<table>" in response.text
    assert "<code>x</code>" in response.text

def test_named_doc(client):
    response = client.get("/help/other")

    assert response.status_code == 200
    assert "<title>Other page</title>" in response.text

def test_index_back_link_goes_to_parent_of_mount_point(client):
    assert 'href="/" class="back"' in client.get("/help").text

def test_nested_mount_back_link(docs_dir):
    app = FastAPI()
    app.include_router(HelpRoutes(docs_dir).router, prefix="/alarm/help")
    client = TestClient(app)

    assert 'href="/alarm" class="back"' in client.get("/alarm/help").text
    assert 'href="/alarm/help" class="back"' in client.get("/alarm/help/other").text

def test_unknown_doc_is_404(client):
    assert client.get("/help/missing").status_code == 404
    assert client.get("/help/secret").status_code == 404
    assert client.get("/help/..%2Fpyproject").status_code == 404

def test_real_docs_dir_has_index():
    assert (HelpRoutes().docs_dir / "index.md").exists()
