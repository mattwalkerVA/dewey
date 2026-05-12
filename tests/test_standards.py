from tools.standards import search_standards, search_wida


def test_search_standards_filters_by_subject_and_grade():
    results = search_standards("multiplication", subject="Math", grade="4")

    assert results
    assert all(item["subject"] == "Math" for item in results)
    assert all(item["grade"] == "4" for item in results)


def test_search_wida_filters_by_level_and_domain():
    results = search_wida(level=2, domain="Writing")

    assert results
    assert all(item["level"] == 2 for item in results)
    assert all(item["domain"] == "Writing" for item in results)
