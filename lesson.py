"""Lesson generator: builds structured Dewey lesson plans on demand.

Used by the dashboard's POST /api/lesson endpoint. Pure-function-friendly so
the streaming endpoint and the tests can both drive it.
"""

import re
from collections.abc import Iterable, Iterator
from typing import Any

import anthropic

import config
from prompts import LESSON_PLAN_SYSTEM_PROMPT, LESSON_VALIDATION_FEEDBACK_PROMPT
from tools import standards


VALID_TIMES = {45, 90}
VALID_KLU = {"Narrate", "Inform", "Explain", "Argue"}
VALID_SUBJECTS = {"ELA", "Math", "Science", "Social Studies", "Other"}
VALID_GRADES = {"K", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"}

MOMENT_BUDGETS: dict[int, dict[str, int]] = {
    45: {"Preparing": 10, "Interacting": 25, "Extending": 10},
    90: {"Preparing": 15, "Interacting": 55, "Extending": 20},
}

PROTOCOL_PALETTE = [
    "Turn-and-Talk",
    "Discussion Move Cards",
    "Stronger & Clearer Each Time",
    "Anticipatory Guide",
    "Write-Converse-Write",
    "Source Triangulation",
    "Visual-First Reading",
    "Quick-Writes by Level",
    "Jigsaw",
]


def ferpa_filter(text: str) -> tuple[str, bool]:
    """Strip likely student PII from a free-text field."""
    cleaned = text or ""
    modified = False
    for pattern in config.FERPA_PATTERNS:
        if pattern.search(cleaned):
            cleaned = pattern.sub("[REDACTED]", cleaned)
            modified = True
    return cleaned, modified


def validate_input(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Coerce and validate the request body. Returns (clean_params, errors)."""
    errors: list[str] = []

    standard = str(payload.get("standard", "") or "").strip()
    objective = str(payload.get("objective", "") or "").strip()
    prompt = str(payload.get("prompt", "") or "").strip()
    grade = str(payload.get("grade", "") or "").strip()
    subject = str(payload.get("subject", "") or "").strip()
    klu = str(payload.get("klu", "") or "").strip()

    try:
        time_minutes = int(payload.get("timeMinutes", 0))
    except (TypeError, ValueError):
        time_minutes = 0

    raw_levels = payload.get("widaLevels") or []
    wida_min = wida_max = 0
    if isinstance(raw_levels, list) and len(raw_levels) >= 2:
        try:
            wida_min = int(raw_levels[0])
            wida_max = int(raw_levels[1])
        except (TypeError, ValueError):
            wida_min = wida_max = 0
    if wida_min and wida_max and wida_min > wida_max:
        wida_min, wida_max = wida_max, wida_min

    if not objective:
        errors.append("objective is required")
    if grade not in VALID_GRADES:
        errors.append("grade must be one of " + ", ".join(sorted(VALID_GRADES)))
    if subject and subject not in VALID_SUBJECTS:
        errors.append("subject must be one of " + ", ".join(sorted(VALID_SUBJECTS)))
    if klu and klu not in VALID_KLU:
        errors.append("klu must be one of " + ", ".join(sorted(VALID_KLU)))
    if time_minutes not in VALID_TIMES:
        errors.append("timeMinutes must be 45 or 90")
    if not (1 <= wida_min <= 6 and 1 <= wida_max <= 6):
        errors.append("widaLevels must be a [min, max] pair within 1-6")

    return (
        {
            "standard": standard,
            "objective": objective,
            "prompt": prompt,
            "grade": grade,
            "subject": subject or "Other",
            "klu": klu or "Explain",
            "time_minutes": time_minutes,
            "wida_min": wida_min,
            "wida_max": wida_max,
        },
        errors,
    )


_DISCUSSION_HEADING = re.compile(
    r"^####\s+Discussion\s+(\d+)\s*[-–—]\s*([^(]+?)\s*\((\d+)\s*min\)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_MOMENT_HEADING = re.compile(
    r"^###\s+(Preparing|Interacting|Extending)\s*\((\d+)\s*min\)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _protocol_in_palette(name: str) -> bool:
    needle = name.strip().lower()
    return any(p.lower() in needle or needle in p.lower() for p in PROTOCOL_PALETTE)


def validate_output(markdown: str, params: dict[str, Any]) -> list[str]:
    """Return a list of contract violations in the generated lesson."""
    violations: list[str] = []

    discussions = _DISCUSSION_HEADING.findall(markdown)
    if len(discussions) != 3:
        violations.append(
            f"Expected exactly 3 Discussion sections, found {len(discussions)}."
        )

    if len(discussions) == 3:
        protocols = {d[1].strip().lower() for d in discussions}
        if len(protocols) < 2:
            violations.append(
                "Use at least two different discussion protocols across the three pieces."
            )

    for _, name, _ in discussions:
        if not _protocol_in_palette(name):
            violations.append(
                f"Discussion protocol '{name.strip()}' is not in the supported palette."
            )

    if params["time_minutes"] == 45:
        for _, name, _ in discussions:
            if "jigsaw" in name.lower():
                violations.append("Jigsaw is only allowed in 90-minute lessons.")

    moments = _MOMENT_HEADING.findall(markdown)
    expected = MOMENT_BUDGETS.get(params["time_minutes"], {})
    found = {label.capitalize(): int(minutes) for label, minutes in moments}
    for label, budget in expected.items():
        actual = found.get(label)
        if actual != budget:
            violations.append(
                f"Moment '{label}' should be {budget} min (found {actual if actual is not None else 'missing'})."
            )

    for level in range(params["wida_min"], params["wida_max"] + 1):
        pattern = rf"Stems\s*\(\s*WIDA\s*{level}\s*\)\s*:"
        # Need 3 stem bullets, one per discussion piece
        matches = re.findall(pattern, markdown, re.IGNORECASE)
        if len(matches) < 3:
            violations.append(
                f"Need a 'Stems (WIDA {level}):' bullet in every discussion piece "
                f"(found {len(matches)} of 3)."
            )

    return violations


def _format_wida_block(wida_min: int, wida_max: int) -> str:
    if not (wida_min and wida_max):
        return "  (no descriptors loaded)"
    lines: list[str] = []
    for level in range(wida_min, wida_max + 1):
        for desc in standards.search_wida(level=level)[:4]:
            lines.append(
                f"  - L{desc['level']} {desc['domain']}: {desc['descriptor']}"
            )
    return "\n".join(lines) if lines else "  (no descriptors loaded)"


def _resolve_standard(standard: str, subject: str, grade: str) -> str:
    if not standard:
        return "(none provided)"
    matches = standards.search_standards(query=standard, subject=subject, grade=grade)
    if not matches:
        return standard
    top = matches[0]
    return f"{top['code']} - {top['strand']}: {top['text']}"


def build_system_prompt(params: dict[str, Any]) -> str:
    """Render LESSON_PLAN_SYSTEM_PROMPT with input and reference data."""
    budgets = MOMENT_BUDGETS[params["time_minutes"]]
    return LESSON_PLAN_SYSTEM_PROMPT.format(
        standard=_resolve_standard(params["standard"], params["subject"], params["grade"]),
        objective=params["objective"],
        prompt=params["prompt"] or "(no additional teacher context)",
        grade=params["grade"],
        subject=params["subject"],
        wida_min=params["wida_min"],
        wida_max=params["wida_max"],
        klu=params["klu"],
        time_minutes=params["time_minutes"],
        preparing_min=budgets["Preparing"],
        interacting_min=budgets["Interacting"],
        extending_min=budgets["Extending"],
        wida_descriptors=_format_wida_block(params["wida_min"], params["wida_max"]),
    )


def _stream_messages(client: Any, system: str, messages: list[dict]) -> Iterator[str]:
    """Yield text chunks from a single Anthropic streaming call."""
    with client.messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=4096,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def generate_lesson_stream(
    params: dict[str, Any],
    client: Any = None,
) -> Iterator[dict[str, Any]]:
    """Stream a lesson plan event-by-event.

    Yields dicts:
      {"type": "chunk", "text": "..."}
      {"type": "notice", "text": "..."}            (e.g. retry banner)
      {"type": "done", "markdown": "...", "violations": [...]}
      {"type": "error", "message": "..."}
    """
    if client is None:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    system = build_system_prompt(params)
    user_msg = (
        f"Draft the lesson now. Time budget: {params['time_minutes']} minutes. "
        f"Exactly three discussion pieces, one per moment."
    )

    try:
        chunks: list[str] = []
        for text in _stream_messages(client, system, [{"role": "user", "content": user_msg}]):
            chunks.append(text)
            yield {"type": "chunk", "text": text}

        markdown = "".join(chunks)
        violations = validate_output(markdown, params)

        if violations:
            yield {
                "type": "notice",
                "text": "Draft missed the contract; retrying with corrections.",
            }
            feedback = LESSON_VALIDATION_FEEDBACK_PROMPT.format(
                violations="\n".join(f"- {v}" for v in violations),
                previous_draft=markdown,
            )
            retry_chunks: list[str] = []
            for text in _stream_messages(
                client,
                system,
                [
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": markdown},
                    {"role": "user", "content": feedback},
                ],
            ):
                retry_chunks.append(text)
                yield {"type": "chunk", "text": text}
            markdown = "".join(retry_chunks)
            violations = validate_output(markdown, params)

        yield {"type": "done", "markdown": markdown, "violations": violations}
    except Exception as exc:
        yield {"type": "error", "message": f"Lesson generation failed: {exc}"}


def coalesce_events(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Drain a stream and return the final result. Convenience for tests."""
    text_parts: list[str] = []
    final: dict[str, Any] = {"markdown": "", "violations": []}
    for event in events:
        if event["type"] == "chunk":
            text_parts.append(event["text"])
        elif event["type"] == "done":
            final = {"markdown": event["markdown"], "violations": event["violations"]}
        elif event["type"] == "error":
            final = {"markdown": "".join(text_parts), "violations": [event["message"]]}
    return final
