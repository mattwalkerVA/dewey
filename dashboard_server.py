"""Local dashboard server for Dewey.

This intentionally uses the Python standard library so the dashboard can run
without adding a separate backend framework dependency.
"""

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Iterator
from urllib.parse import parse_qs, urlparse

import config
import lesson
from memory import Memory
from tools import filesystem, standards


DASHBOARD_DIR = Path(str(files("dashboard")))
TEACHING_TOOLS_DIR = config.BASE_DIR / "teaching_tools"


def json_response(status: int, payload: object) -> tuple[int, str, bytes]:
    """Serialize an API response."""
    return status, "application/json; charset=utf-8", json.dumps(payload).encode("utf-8")


def read_json_body(body: bytes) -> dict:
    """Parse a JSON request body, returning an empty dict for blank bodies."""
    if not body:
        return {}
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object.")
    return parsed


def get_query(params: dict[str, list[str]], name: str, default: str = "") -> str:
    """Return the first query parameter value."""
    values = params.get(name)
    if not values:
        return default
    return values[0]


def profile_payload() -> dict:
    """Return profile notes for the dashboard."""
    memory = Memory(str(config.DB_PATH))
    try:
        return {"items": memory.get_all(config.PROFILE_COLLECTION)}
    finally:
        memory.close()


def delete_profile_payload() -> dict:
    """Delete profile notes and return a deletion summary."""
    memory = Memory(str(config.DB_PATH))
    try:
        deleted = memory.delete_collection(config.PROFILE_COLLECTION)
        return {"deleted": deleted}
    finally:
        memory.close()


def handle_api_request(method: str, raw_path: str, body: bytes = b"") -> tuple[int, str, bytes]:
    """Handle a dashboard API request without depending on an HTTP server."""
    parsed = urlparse(raw_path)
    query = parse_qs(parsed.query)

    try:
        if method == "GET" and parsed.path == "/api/profile":
            return json_response(HTTPStatus.OK, profile_payload())

        if method == "DELETE" and parsed.path == "/api/profile":
            return json_response(HTTPStatus.OK, delete_profile_payload())

        if method == "GET" and parsed.path == "/api/plans":
            return json_response(HTTPStatus.OK, {"items": filesystem.list_lesson_plans()})

        if method == "POST" and parsed.path == "/api/plans":
            payload = read_json_body(body)
            title = str(payload.get("title", "")).strip() or "Untitled Lesson"
            content = str(payload.get("content", "")).strip()
            if not content:
                return json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Plan content is required."},
                )
            path = filesystem.save_lesson_plan(
                title=title,
                content=content,
                grade=str(payload.get("grade", "")).strip(),
                subject=str(payload.get("subject", "")).strip(),
            )
            return json_response(HTTPStatus.CREATED, {"path": path})

        if method == "GET" and parsed.path == "/api/standards":
            query_text = get_query(query, "query")
            if not query_text:
                return json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Query is required."},
                )
            results = standards.search_standards(
                query=query_text,
                subject=get_query(query, "subject"),
                grade=get_query(query, "grade"),
            )
            return json_response(HTTPStatus.OK, {"items": results})

        if method == "GET" and parsed.path == "/api/wida":
            raw_level = get_query(query, "level", "0")
            try:
                level = int(raw_level or "0")
            except ValueError:
                return json_response(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Level must be a number from 0 to 6."},
                )
            results = standards.search_wida(
                level=level,
                domain=get_query(query, "domain"),
                grade_band=get_query(query, "grade_band"),
            )
            return json_response(HTTPStatus.OK, {"items": results})

    except json.JSONDecodeError:
        return json_response(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
    except ValueError as exc:
        return json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
    except Exception as exc:
        return json_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            {"error": f"Dashboard request failed: {exc}"},
        )

    return json_response(HTTPStatus.NOT_FOUND, {"error": "Not found."})


def _sse(event_type: str, payload: dict) -> bytes:
    """Format a single Server-Sent Event frame."""
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n".encode("utf-8")


def stream_lesson(events: Iterator[dict]) -> Iterator[bytes]:
    """Adapt lesson.generate_lesson_stream events to SSE frames."""
    for event in events:
        kind = event["type"]
        if kind == "chunk":
            yield _sse("chunk", {"text": event["text"]})
        elif kind == "notice":
            yield _sse("notice", {"text": event["text"]})
        elif kind == "done":
            yield _sse(
                "done",
                {"markdown": event["markdown"], "violations": event["violations"]},
            )
        elif kind == "error":
            yield _sse("error", {"message": event["message"]})


class DashboardHandler(SimpleHTTPRequestHandler):
    """Serve the dashboard static files and API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.write_api_response("GET")
            return
        if self.path.startswith("/teaching_tools/"):
            self.serve_teaching_tool()
            return
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path == "/api/lesson":
            self.stream_lesson_response()
            return
        self.write_api_response("POST", self.read_body())

    def do_DELETE(self):
        self.write_api_response("DELETE")

    def read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length else b""

    def write_api_response(self, method: str, body: bytes = b"") -> None:
        status, content_type, payload = handle_api_request(method, self.path, body)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def serve_teaching_tool(self) -> None:
        """Serve a printable HTML card from teaching_tools/ safely."""
        rel = urlparse(self.path).path.removeprefix("/teaching_tools/")
        target = (TEACHING_TOOLS_DIR / rel).resolve()
        try:
            target.relative_to(TEACHING_TOOLS_DIR.resolve())
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN, "Path escapes teaching_tools.")
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Teaching tool not found.")
            return
        content_type, _ = mimetypes.guess_type(target.name)
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def stream_lesson_response(self) -> None:
        """Validate input and stream a generated lesson plan as SSE."""
        try:
            body = self.read_body()
            payload = read_json_body(body)
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        ferpa_modified = False
        for field in ("objective", "prompt"):
            value = str(payload.get(field, "") or "")
            cleaned, was_modified = lesson.ferpa_filter(value)
            payload[field] = cleaned
            ferpa_modified = ferpa_modified or was_modified

        params, errors = lesson.validate_input(payload)
        if errors:
            response = json.dumps({"errors": errors}).encode("utf-8")
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        if ferpa_modified:
            self.wfile.write(
                _sse("notice", {"text": "Possible student PII was removed before sending."})
            )
            self.wfile.flush()

        try:
            for frame in stream_lesson(lesson.generate_lesson_stream(params)):
                self.wfile.write(frame)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Client closed the stream; nothing more to do.
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Dewey dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Dewey dashboard running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
