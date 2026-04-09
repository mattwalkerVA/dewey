from agent import ferpa_filter, sanitize_for_storage


def test_ferpa_filter_redacts_student_identifier_patterns():
    cleaned, modified = ferpa_filter("student id: 12345 needs support tomorrow")

    assert modified is True
    assert "[REDACTED]" in cleaned
    assert "12345" not in cleaned


def test_sanitize_for_storage_uses_ferpa_filter():
    cleaned, modified = sanitize_for_storage("student id: 67890 appears in notes")

    assert modified is True
    assert cleaned == "[REDACTED] appears in notes"
