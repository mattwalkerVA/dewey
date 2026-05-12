"""Tests for the lesson generator: input validation, output validation,
and the streaming endpoint with a fake Anthropic client.
"""

import json
from contextlib import contextmanager

import pytest

import lesson


GOOD_PARAMS_45 = {
    "standard": "",
    "objective": "Explain how setting shapes the mood of a short story.",
    "prompt": "Use the class anchor text.",
    "grade": "5",
    "subject": "ELA",
    "klu": "Explain",
    "timeMinutes": 45,
    "widaLevels": [2, 4],
}


def _good_lesson_45() -> str:
    """A lesson that passes validate_output for the 45-min, WIDA 2-4 contract."""
    return (
        "# Setting Shapes Mood\n\n"
        "## Objectives\n- Content: ...\n- Language: ... (KLU: Explain)\n\n"
        "## Standard\n- ...\n\n"
        "## Materials\n- ...\n\n"
        "## Lesson Arc\n\n"
        "### Preparing (10 min)\nTeacher does ...\n\n"
        "#### Discussion 1 - Anticipatory Guide (4 min)\n"
        "- Prompt: Do dark settings always signal sadness?\n"
        "- Stems (WIDA 2): I agree because ___.\n"
        "- Stems (WIDA 3): I think the setting suggests ___.\n"
        "- Stems (WIDA 4): The author's choice of setting positions the reader to feel ___.\n"
        "- Move cards in play: Probe, Build\n"
        "- Timing: 4 min within Preparing.\n"
        "- Teacher move: listen for evidence.\n"
        "- Companion tool: [Anticipatory Guide](/teaching_tools/anticipatory-guide-expressions.html)\n\n"
        "### Interacting (25 min)\nTeacher does ...\n\n"
        "#### Discussion 2 - Discussion Move Cards (8 min)\n"
        "- Prompt: How does paragraph 3 establish the mood?\n"
        "- Stems (WIDA 2): The mood is ___.\n"
        "- Stems (WIDA 3): The mood feels ___ because ___.\n"
        "- Stems (WIDA 4): The author establishes mood through ___.\n"
        "- Move cards in play: Probe, Paraphrase, Build, Challenge\n"
        "- Timing: 8 min within Interacting.\n"
        "- Teacher move: cold-call after wait time.\n"
        "- Companion tool: [Discussion Move Cards](/teaching_tools/co-teaching/10-discussion-move-cards.html)\n\n"
        "### Extending (10 min)\nTeacher does ...\n\n"
        "#### Discussion 3 - Write-Converse-Write (6 min)\n"
        "- Prompt: How would changing the setting change the mood?\n"
        "- Stems (WIDA 2): If the setting were ___, the mood would be ___.\n"
        "- Stems (WIDA 3): Changing the setting to ___ would shift the mood to ___.\n"
        "- Stems (WIDA 4): Substituting ___ as the setting would reframe the mood from ___ to ___.\n"
        "- Move cards in play: Build, Clarify\n"
        "- Timing: 6 min within Extending.\n"
        "- Teacher move: capture exemplar revisions.\n"
        "- Companion tool: [Write-Converse-Write](/teaching_tools/write-converse-write-assessment.html)\n\n"
        "## Differentiation\n- ...\n\n"
        "## Assessment\n- ...\n"
    )


def test_validate_input_accepts_good_payload():
    params, errors = lesson.validate_input(GOOD_PARAMS_45)
    assert errors == []
    assert params["time_minutes"] == 45
    assert params["wida_min"] == 2 and params["wida_max"] == 4
    assert params["klu"] == "Explain"


def test_validate_input_rejects_bad_time_and_klu():
    bad = dict(GOOD_PARAMS_45, timeMinutes=60, klu="Sing")
    _, errors = lesson.validate_input(bad)
    assert any("timeMinutes" in e for e in errors)
    assert any("klu" in e for e in errors)


def test_validate_input_swaps_inverted_wida_range():
    params, errors = lesson.validate_input(dict(GOOD_PARAMS_45, widaLevels=[5, 2]))
    assert errors == []
    assert params["wida_min"] == 2 and params["wida_max"] == 5


def test_validate_input_requires_objective_and_valid_grade():
    bad = dict(GOOD_PARAMS_45, objective="", grade="13")
    _, errors = lesson.validate_input(bad)
    assert any("objective" in e for e in errors)
    assert any("grade" in e for e in errors)


def test_validate_output_passes_on_good_lesson():
    params, _ = lesson.validate_input(GOOD_PARAMS_45)
    assert lesson.validate_output(_good_lesson_45(), params) == []


def test_validate_output_flags_missing_discussion():
    params, _ = lesson.validate_input(GOOD_PARAMS_45)
    markdown = _good_lesson_45().replace(
        "#### Discussion 3 - Write-Converse-Write (6 min)",
        "#### NotADiscussion (6 min)",
    )
    violations = lesson.validate_output(markdown, params)
    assert any("3 Discussion" in v for v in violations)


def test_validate_output_flags_duplicate_protocols():
    params, _ = lesson.validate_input(GOOD_PARAMS_45)
    markdown = _good_lesson_45().replace(
        "Discussion 2 - Discussion Move Cards", "Discussion 2 - Anticipatory Guide"
    ).replace(
        "Discussion 3 - Write-Converse-Write", "Discussion 3 - Anticipatory Guide"
    )
    violations = lesson.validate_output(markdown, params)
    assert any("two different" in v for v in violations)


def test_validate_output_flags_off_palette_protocol():
    params, _ = lesson.validate_input(GOOD_PARAMS_45)
    markdown = _good_lesson_45().replace(
        "Discussion 3 - Write-Converse-Write", "Discussion 3 - Karaoke Time"
    )
    violations = lesson.validate_output(markdown, params)
    assert any("not in the supported palette" in v for v in violations)


def test_validate_output_flags_jigsaw_in_45_min():
    params, _ = lesson.validate_input(GOOD_PARAMS_45)
    markdown = _good_lesson_45().replace(
        "Discussion 3 - Write-Converse-Write", "Discussion 3 - Jigsaw"
    )
    violations = lesson.validate_output(markdown, params)
    assert any("Jigsaw" in v for v in violations)


def test_validate_output_flags_wrong_moment_budget():
    params, _ = lesson.validate_input(GOOD_PARAMS_45)
    markdown = _good_lesson_45().replace("### Preparing (10 min)", "### Preparing (15 min)")
    violations = lesson.validate_output(markdown, params)
    assert any("Preparing" in v and "10 min" in v for v in violations)


def test_validate_output_flags_missing_wida_stems():
    params, _ = lesson.validate_input(dict(GOOD_PARAMS_45, widaLevels=[2, 5]))
    violations = lesson.validate_output(_good_lesson_45(), params)
    assert any("WIDA 5" in v for v in violations)


def test_ferpa_filter_removes_student_name_with_grade():
    cleaned, modified = lesson.ferpa_filter("Maria Lopez's grade dropped this week.")
    assert modified is True
    assert "Maria Lopez" not in cleaned


# --- Streaming with a fake Anthropic client ---


class FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    @property
    def text_stream(self):
        return iter(self._chunks)


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def stream(self, *, model, max_tokens, system, messages):
        self.calls += 1
        index = min(self.calls - 1, len(self._responses) - 1)
        return FakeStream(self._responses[index])


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def test_generate_lesson_stream_single_pass_when_valid():
    params, _ = lesson.validate_input(GOOD_PARAMS_45)
    # Split the good lesson into a few "tokens" to mimic streaming
    full = _good_lesson_45()
    chunks = [full[:500], full[500:1500], full[1500:]]
    client = FakeClient([chunks])

    events = list(lesson.generate_lesson_stream(params, client=client))
    assert client.messages.calls == 1  # No retry
    done = [e for e in events if e["type"] == "done"][0]
    assert done["violations"] == []
    assert done["markdown"] == full


def test_generate_lesson_stream_retries_when_invalid():
    params, _ = lesson.validate_input(GOOD_PARAMS_45)
    bad = _good_lesson_45().replace(
        "#### Discussion 3 - Write-Converse-Write (6 min)",
        "#### Notes (0 min)",
    )
    good = _good_lesson_45()
    client = FakeClient([[bad], [good]])

    events = list(lesson.generate_lesson_stream(params, client=client))
    assert client.messages.calls == 2
    assert any(e["type"] == "notice" for e in events)
    done = [e for e in events if e["type"] == "done"][0]
    assert done["violations"] == []


def test_generate_lesson_stream_reports_error_on_exception():
    params, _ = lesson.validate_input(GOOD_PARAMS_45)

    class ExplodingClient:
        class messages:
            @staticmethod
            def stream(**kwargs):
                raise RuntimeError("boom")

    events = list(lesson.generate_lesson_stream(params, client=ExplodingClient()))
    assert events[-1]["type"] == "error"
    assert "boom" in events[-1]["message"]
