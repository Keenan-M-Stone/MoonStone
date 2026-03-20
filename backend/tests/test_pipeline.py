"""Tests for the MoonStone pipeline (projects, runs, backends)."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_backends():
    res = client.get("/backends")
    assert res.status_code == 200
    data = res.json()
    names = [b["name"] for b in data]
    assert "dummy" in names
    assert "einstein_toolkit" in names


def test_get_backend_capabilities():
    res = client.get("/backends/einstein_toolkit")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "einstein_toolkit"
    assert "metric_types" in data


def test_translate_unknown_backend():
    res = client.post("/backends/nosolver/translate", json={})
    assert res.status_code == 404


def test_translate_dummy():
    res = client.post("/backends/dummy/translate", json={"metric": {"type": "schwarzschild"}})
    assert res.status_code == 200
    data = res.json()
    assert data["backend"] == "dummy"
    assert data.get("translated") is None
    assert any("No server-side translator" in w for w in data.get("warnings", []))


def test_project_and_run_lifecycle():
    # Create project
    res = client.post("/projects", json={"name": "GR test"})
    assert res.status_code == 200
    project = res.json()
    pid = project["id"]

    # Get project
    res = client.get(f"/projects/{pid}")
    assert res.status_code == 200
    assert res.json()["name"] == "GR test"

    # Create run
    spec = {"metric": {"type": "schwarzschild", "mass": 1.0}, "domain": {"size": [10, 10, 10]}}
    res = client.post(f"/projects/{pid}/runs", json={"spec": spec})
    assert res.status_code == 200
    run = res.json()
    rid = run["id"]
    assert run["status"] == "created"

    # Get run
    res = client.get(f"/runs/{rid}")
    assert res.status_code == 200
    assert res.json()["status"] == "created"

    # List artifacts (should be empty outputs initially)
    res = client.get(f"/runs/{rid}/artifacts")
    assert res.status_code == 200


def test_project_not_found():
    res = client.get("/projects/nonexistent")
    assert res.status_code == 404
