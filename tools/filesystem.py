"""Tool: Save lesson plans as structured markdown files."""

import re
from datetime import datetime

import config


def slugify(text: str, max_len: int = 60) -> str:
    """Turn a title into a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:max_len].rstrip("-")


def frontmatter_value(text: str) -> str:
    """Format a simple quoted YAML frontmatter value."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_frontmatter(text: str) -> dict:
    """Extract simple key/value metadata from lesson-plan frontmatter."""
    metadata = {}
    if not text.startswith("---"):
        return metadata
    for line in text.split("\n")[1:]:
        if line.startswith("---"):
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def save_lesson_plan(title: str, content: str, grade: str = "", subject: str = "") -> str:
    """Save a lesson plan as a markdown file.

    Returns the path to the saved file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(title) or "untitled-lesson"
    base_filename = f"{timestamp}_{slug}"
    filepath = config.PLANS_DIR / f"{base_filename}.md"
    suffix = 2
    while filepath.exists():
        filepath = config.PLANS_DIR / f"{base_filename}_{suffix}.md"
        suffix += 1

    # Build frontmatter
    frontmatter_lines = [
        "---",
        f"title: {frontmatter_value(title)}",
        f"date: {timestamp}",
    ]
    if grade:
        frontmatter_lines.append(f"grade: {frontmatter_value(grade)}")
    if subject:
        frontmatter_lines.append(f"subject: {frontmatter_value(subject)}")
    frontmatter_lines.append("---\n")

    full_content = "\n".join(frontmatter_lines) + "\n" + content

    filepath.write_text(full_content, encoding="utf-8")
    return str(filepath)


def list_lesson_plans() -> list[dict]:
    """List all saved lesson plans with metadata."""
    plans = []
    for f in sorted(config.PLANS_DIR.glob("*.md"), reverse=True):
        text = f.read_text(encoding="utf-8")
        metadata = parse_frontmatter(text)
        title = metadata.get("title", f.stem)
        plans.append({
            "filename": f.name,
            "path": str(f),
            "title": title,
            "grade": metadata.get("grade", ""),
            "subject": metadata.get("subject", ""),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return plans


# Tool definitions for Claude API tool_use
TOOLS = [
    {
        "name": "save_lesson_plan",
        "description": (
            "Save a lesson plan as a markdown file in the teacher's local plans "
            "directory. Use this whenever you produce a complete or near-complete "
            "lesson plan that the teacher would want to keep."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short descriptive title for the lesson plan.",
                },
                "content": {
                    "type": "string",
                    "description": "Full lesson plan content in markdown format.",
                },
                "grade": {
                    "type": "string",
                    "description": "Grade level (e.g. '3rd', '9-10', 'K').",
                },
                "subject": {
                    "type": "string",
                    "description": "Subject area (e.g. 'ELA', 'Math', 'Science').",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "list_lesson_plans",
        "description": (
            "List all previously saved lesson plans with their titles, dates, "
            "and file paths. Use this when the teacher asks about past plans."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


def handle_tool_call(name: str, input_data: dict) -> str:
    """Execute a filesystem tool call and return the result as a string."""
    if name == "save_lesson_plan":
        path = save_lesson_plan(
            title=input_data["title"],
            content=input_data["content"],
            grade=input_data.get("grade", ""),
            subject=input_data.get("subject", ""),
        )
        return f"Lesson plan saved to: {path}"

    if name == "list_lesson_plans":
        plans = list_lesson_plans()
        if not plans:
            return "No saved lesson plans yet."
        lines = [f"- **{p['title']}** ({p['filename']})" for p in plans]
        return f"Found {len(plans)} saved plans:\n" + "\n".join(lines)

    return f"Unknown filesystem tool: {name}"
