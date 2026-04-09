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
