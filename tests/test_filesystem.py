from tools import filesystem


def test_save_lesson_plan_writes_frontmatter_and_avoids_collisions(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem.config, "PLANS_DIR", tmp_path)

    first_path = filesystem.save_lesson_plan("Fractions Unit", "# Plan A", grade="4", subject="Math")
    second_path = filesystem.save_lesson_plan("Fractions Unit", "# Plan B", grade="4", subject="Math")

    first_text = (tmp_path / first_path.split("/")[-1]).read_text(encoding="utf-8")

    assert first_path.endswith(".md")
    assert second_path.endswith("_2.md")
    assert 'title: "Fractions Unit"' in first_text
    assert 'grade: "4"' in first_text
    assert 'subject: "Math"' in first_text
    assert "# Plan A" in first_text


def test_save_lesson_plan_uses_fallback_slug_for_empty_title(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem.config, "PLANS_DIR", tmp_path)

    path = filesystem.save_lesson_plan("!!!", "# Plan")

    assert path.endswith("_untitled-lesson.md")
    assert (tmp_path / path.split("/")[-1]).exists()


def test_list_lesson_plans_includes_frontmatter_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem.config, "PLANS_DIR", tmp_path)
    filesystem.save_lesson_plan("Ecosystems", "# Plan", grade="5", subject="Science")

    plans = filesystem.list_lesson_plans()

    assert plans == [
        {
            "filename": plans[0]["filename"],
            "path": plans[0]["path"],
            "title": "Ecosystems",
            "grade": "5",
            "subject": "Science",
            "modified": plans[0]["modified"],
        }
    ]


def test_read_lesson_plan_strips_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem.config, "PLANS_DIR", tmp_path)
    saved_path = filesystem.save_lesson_plan(
        "Inference Lesson",
        "# Inference\n\n## Objectives\n- Content: ...",
        grade="5",
        subject="ELA",
    )
    filename = saved_path.split("/")[-1]

    plan = filesystem.read_lesson_plan(filename)

    assert plan["title"] == "Inference Lesson"
    assert plan["grade"] == "5"
    assert plan["subject"] == "ELA"
    assert plan["content"].startswith("# Inference")
    assert "title:" not in plan["content"]


def test_read_lesson_plan_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem.config, "PLANS_DIR", tmp_path)
    import pytest

    with pytest.raises(FileNotFoundError):
        filesystem.read_lesson_plan("../config.py")


def test_read_lesson_plan_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(filesystem.config, "PLANS_DIR", tmp_path)
    import pytest

    with pytest.raises(FileNotFoundError):
        filesystem.read_lesson_plan("does-not-exist.md")
