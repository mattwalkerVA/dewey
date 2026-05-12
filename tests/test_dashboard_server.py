import io
import json

import config
import dashboard_server
import lesson
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


class _FakeRequest:
    """Minimal request stand-in for exercising DashboardHandler without sockets."""

    def __init__(self, method: str, path: str, body: bytes = b""):
        headers = f"{method} {path} HTTP/1.1\r\nContent-Length: {len(body)}\r\n\r\n"
        self._rfile = io.BytesIO(headers.encode("utf-8") + body)

    def makefile(self, mode, *args, **kwargs):
        if "b" not in mode:
            raise NotImplementedError
        if "r" in mode:
            return self._rfile
        return io.BytesIO()


def _drive_handler(method: str, path: str, body: bytes = b"") -> tuple[int, dict[str, str], bytes]:
    """Run DashboardHandler against an in-memory request and capture the response."""

    class CapturingHandler(dashboard_server.DashboardHandler):
        def setup(self):
            self.rfile = self.request._rfile
            self.wfile = io.BytesIO()
            self.connection = None

        def finish(self):
            pass

        def log_message(self, format, *args):
            pass

    request = _FakeRequest(method, path, body)
    handler = CapturingHandler(request, ("127.0.0.1", 0), None)
    raw = handler.wfile.getvalue()
    head, _, payload = raw.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    status_line = lines[0].decode("latin-1")
    status = int(status_line.split()[1])
    headers = {}
    for line in lines[1:]:
        if b":" in line:
            key, _, value = line.partition(b":")
            headers[key.decode("latin-1").strip()] = value.decode("latin-1").strip()
    return status, headers, payload


def test_dashboard_serves_teaching_tool_file(tmp_path, monkeypatch):
    configure_temp_paths(tmp_path, monkeypatch)
    status, headers, body = _drive_handler(
        "GET", "/teaching_tools/co-teaching/10-discussion-move-cards.html"
    )
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert b"Discussion Move Cards" in body


def test_dashboard_rejects_teaching_tool_path_traversal(tmp_path, monkeypatch):
    configure_temp_paths(tmp_path, monkeypatch)
    status, _, _ = _drive_handler(
        "GET", "/teaching_tools/../config.py"
    )
    assert status in {403, 404}


def test_dashboard_lesson_rejects_invalid_input(tmp_path, monkeypatch):
    configure_temp_paths(tmp_path, monkeypatch)
    body = json.dumps({"objective": "", "grade": "13", "timeMinutes": 60}).encode("utf-8")
    status, headers, payload = _drive_handler("POST", "/api/lesson", body)
    assert status == 400
    assert headers["Content-Type"].startswith("application/json")
    decoded = json.loads(payload)
    assert "errors" in decoded
    assert any("timeMinutes" in e for e in decoded["errors"])


def test_dashboard_lesson_streams_sse(tmp_path, monkeypatch):
    configure_temp_paths(tmp_path, monkeypatch)

    def fake_generate(params, client=None):
        yield {"type": "chunk", "text": "hello "}
        yield {"type": "chunk", "text": "world"}
        yield {"type": "done", "markdown": "hello world", "violations": []}

    monkeypatch.setattr(lesson, "generate_lesson_stream", fake_generate)
    monkeypatch.setattr(dashboard_server.lesson, "generate_lesson_stream", fake_generate)

    body = json.dumps({
        "objective": "Test objective",
        "grade": "5",
        "subject": "ELA",
        "klu": "Explain",
        "timeMinutes": 45,
        "widaLevels": [2, 4],
    }).encode("utf-8")

    status, headers, payload = _drive_handler("POST", "/api/lesson", body)
    assert status == 200
    assert headers["Content-Type"].startswith("text/event-stream")
    text = payload.decode("utf-8")
    assert "event: chunk" in text
    assert "hello " in text
    assert "world" in text
    assert "event: done" in text


def test_dashboard_lesson_emits_ferpa_notice(tmp_path, monkeypatch):
    configure_temp_paths(tmp_path, monkeypatch)

    def fake_generate(params, client=None):
        yield {"type": "done", "markdown": "ok", "violations": []}

    monkeypatch.setattr(dashboard_server.lesson, "generate_lesson_stream", fake_generate)

    body = json.dumps({
        "objective": "Plan reading for Maria Lopez's grade level.",
        "grade": "5",
        "subject": "ELA",
        "klu": "Explain",
        "timeMinutes": 45,
        "widaLevels": [2, 4],
    }).encode("utf-8")

    status, _, payload = _drive_handler("POST", "/api/lesson", body)
    assert status == 200
    text = payload.decode("utf-8")
    assert "event: notice" in text
    assert "PII" in text
