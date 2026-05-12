"""Tool: Search Virginia SOLs and WIDA Can-Do descriptors."""

import json
from functools import lru_cache

import config


DATA_DIR = config.BASE_DIR / "data"


@lru_cache(maxsize=1)
def load_va_sols() -> list[dict]:
    """Load Virginia SOL reference data from disk."""
    return json.loads((DATA_DIR / "va_sols.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_wida_descriptors() -> list[dict]:
    """Load WIDA descriptor reference data from disk."""
    return json.loads((DATA_DIR / "wida_descriptors.json").read_text(encoding="utf-8"))


def search_standards(
    query: str,
    subject: str = "",
    grade: str = "",
) -> list[dict]:
    """Search Virginia SOLs by keyword, subject, and/or grade."""
    query_lower = query.lower()
    keywords = query_lower.split()
    results = []

    for sol in load_va_sols():
        if subject and subject.lower() not in sol["subject"].lower():
            continue
        if grade and grade.lower() not in sol["grade"].lower():
            continue

        searchable = f"{sol['code']} {sol['strand']} {sol['text']}".lower()
        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            results.append({**sol, "_score": score})

    results.sort(key=lambda x: x["_score"], reverse=True)
    for result in results:
        result.pop("_score", None)
    return results[:10]


def search_wida(
    level: int = 0,
    domain: str = "",
    grade_band: str = "",
) -> list[dict]:
    """Search WIDA Can-Do descriptors by proficiency level and/or domain."""
    results = []
    for desc in load_wida_descriptors():
        if level and desc["level"] != level:
            continue
        if domain and domain.lower() not in desc["domain"].lower():
            continue
        if grade_band and grade_band not in desc["grade_band"]:
            continue
        results.append(desc)
    return results


TOOLS = [
    {
        "name": "search_standards",
        "description": (
            "Search Virginia Standards of Learning (SOLs) by keyword, subject, "
            "and grade level. Returns matching standards with code, strand, and "
            "full text. Use this when aligning lessons to state standards."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords to search for (e.g. 'reading comprehension', 'fractions', 'scientific method').",
                },
                "subject": {
                    "type": "string",
                    "description": "Filter by subject: ELA, Math, Science, History. Leave empty for all.",
                },
                "grade": {
                    "type": "string",
                    "description": "Filter by grade level (e.g. '3', '6-8', '9-12', 'K'). Leave empty for all.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_wida",
        "description": (
            "Look up WIDA Can-Do descriptors by proficiency level (1-6) and "
            "language domain (Listening, Speaking, Reading, Writing). Use this "
            "when designing language objectives or differentiation strategies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "integer",
                    "description": "WIDA proficiency level 1-6. Use 0 for all levels.",
                },
                "domain": {
                    "type": "string",
                    "description": "Language domain: Listening, Speaking, Reading, or Writing. Leave empty for all.",
                },
                "grade_band": {
                    "type": "string",
                    "description": "Optional grade band filter (for current data this is typically 'K-12').",
                },
            },
        },
    },
]


def handle_tool_call(name: str, input_data: dict) -> str:
    """Execute a standards tool call and return the result as a string."""
    if name == "search_standards":
        results = search_standards(
            query=input_data["query"],
            subject=input_data.get("subject", ""),
            grade=input_data.get("grade", ""),
        )
        if not results:
            return "No matching Virginia SOLs found. Try broader keywords or a different grade band."
        lines = []
        for result in results:
            lines.append(
                f"**{result['code']}** ({result['subject']}, Grade {result['grade']}) - {result['strand']}"
            )
            lines.append(f"  {result['text']}\n")
        return "\n".join(lines)

    if name == "search_wida":
        results = search_wida(
            level=input_data.get("level", 0),
            domain=input_data.get("domain", ""),
            grade_band=input_data.get("grade_band", ""),
        )
        if not results:
            return "No matching WIDA descriptors found."
        lines = []
        for result in results:
            lines.append(
                f"**Level {result['level']} - {result['domain']}**: {result['descriptor']}"
            )
        return "\n".join(lines)

    return f"Unknown standards tool: {name}"
