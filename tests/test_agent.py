import config
from agent import (
    ferpa_filter,
    format_lesson_plan_list,
    format_teacher_profile,
    handle_memory_delete,
    sanitize_for_storage,
)
from memory import Memory
from tools import filesystem


def test_ferpa_filter_redacts_student_identifier_patterns():
    cleaned, modified = ferpa_filter("student id: 12345 needs support tomorrow")

    assert modified is True
    assert "[REDACTED]" in cleaned
    assert "12345" not in cleaned


def test_sanitize_for_storage_uses_ferpa_filter():
    cleaned, modified = sanitize_for_storage("student id: 67890 appears in notes")

    assert modified is True
    assert cleaned == "[REDACTED] appears in notes"


def test_ferpa_filter_redacts_named_iep_support_phrasing():
    cleaned, modified = ferpa_filter("Maria Lopez has an IEP and needs visuals")

    assert modified is True
    assert cleaned == "[REDACTED] and needs visuals"


def test_ferpa_filter_redacts_student_email_context():
    cleaned, modified = ferpa_filter("student email: alex.2029@school.edu needs support")

    assert modified is True
    assert "[REDACTED]" in cleaned
    assert "alex.2029@school.edu" not in cleaned


def test_ferpa_filter_redacts_504_name_reference():
    cleaned, modified = ferpa_filter("504 plan for Jordan Smith includes breaks")

    assert modified is True
    assert cleaned == "[REDACTED] includes breaks"


def test_ferpa_filter_does_not_redact_framework_terms():
    cleaned, modified = ferpa_filter("WIDA Level 2 students need sentence frames")

    assert modified is False
    assert cleaned == "WIDA Level 2 students need sentence frames"


def test_ferpa_reminder_is_terminal_safe_ascii():
    config.FERPA_REMINDER.encode("ascii")


def test_format_lesson_plan_list_shows_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem.config, "PLANS_DIR", tmp_path)
    filesystem.save_lesson_plan("Weather Patterns", "# Plan", grade="3", subject="Science")

    output = format_lesson_plan_list()

    assert "Weather Patterns (Grade 3, Science)" in output
    assert str(tmp_path) in output


def test_profile_format_and_delete_helpers(tmp_path):
    memory = Memory(db_path=str(tmp_path / "memory.db"))
    memory.store("Teacher works with grade 4 EL students.", "teacher_profile", category="profile")

    assert "Teacher works with grade 4 EL students." in format_teacher_profile(memory)
    assert handle_memory_delete(memory, "profile") == "Deleted 1 teacher profile note."
    assert format_teacher_profile(memory) == "No teacher profile notes saved yet."

    memory.close()
