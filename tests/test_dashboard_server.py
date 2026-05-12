import json

import config
import dashboard_server
from memory import Memory
from tools import filesystem


def configure_temp_paths(tmp_path, monkeypatch):
    db_dir = tmp_path / "db"
    plans_dir = tmp_path / "plans"
    db_dir.mkdir()
    plans_dir.mkdir()
    db_path = db_dir / "memory.db"

    monkeypatch.setattr(config, "DB_DIR", db_dir)
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "PLANS_DIR", plans_dir)
    monkeypatch.setattr(dashboard_server.config, "DB_DIR", db_dir)
    monkeypatch.setattr(dashboard_server.config, "DB_PATH", db_path)
    monkeypatch.setattr(dashboard_server.config, "PLANS_DIR", plans_dir)
    monkeypatch.setattr(filesystem.config, "PLANS_DIR", plans_dir)

    return db_path, plans_dir


def decode(response):
    status, content_type, body = response
    return status, content_type, json.loads(body.decode("utf-8"))


def test_dashboard_profile_read_and_delete(tmp_path, monkeypatch):
    db_path, _ = configure_temp_paths(tmp_path, monkeypatch)
    memory = Memory(str(db_path))
    memory.store("Teacher teaches grade 4 math.", config.PROFILE_COLLECTION, category="profile")
    memory.close()

    status, content_type, payload = decode(
        dashboard_server.handle_api_request("GET", "/api/profile")
    )

    assert status == 200
    assert content_type.startswith("application/json")
    assert payload["items"][0]["content"] == "Teacher teaches grade 4 math."

    status, _, payload = decode(dashboard_server.handle_api_request("DELETE", "/api/profile"))

    assert status == 200
    assert payload == {"deleted": 1}


def test_dashboard_plan_save_and_list(tmp_path, monkeypatch):
    _, plans_dir = configure_temp_paths(tmp_path, monkeypatch)
    body = json.dumps({
        "title": "Weather Lesson",
        "content": "# Plan",
        "grade": "3",
        "subject": "Science",
    }).encode("utf-8")

    status, _, payload = decode(dashboard_server.handle_api_request("POST", "/api/plans", body))

    assert status == 201
    assert payload["path"].startswith(str(plans_dir))

    status, _, payload = decode(dashboard_server.handle_api_request("GET", "/api/plans"))

    assert status == 200
    assert payload["items"][0]["title"] == "Weather Lesson"
    assert payload["items"][0]["grade"] == "3"
    assert payload["items"][0]["subject"] == "Science"


def test_dashboard_plan_save_requires_content(tmp_path, monkeypatch):
    configure_temp_paths(tmp_path, monkeypatch)
    body = json.dumps({"title": "Empty"}).encode("utf-8")

    status, _, payload = decode(dashboard_server.handle_api_request("POST", "/api/plans", body))

    assert status == 400
    assert payload == {"error": "Plan content is required."}


def test_dashboard_standards_and_wida_search(tmp_path, monkeypatch):
    configure_temp_paths(tmp_path, monkeypatch)

    status, _, sol_payload = decode(
        dashboard_server.handle_api_request(
            "GET",
            "/api/standards?query=multiplication&subject=Math&grade=4",
        )
    )
    status_wida, _, wida_payload = decode(
        dashboard_server.handle_api_request("GET", "/api/wida?level=2&domain=Writing")
    )

    assert status == 200
    assert sol_payload["items"]
    assert status_wida == 200
    assert wida_payload["items"]
