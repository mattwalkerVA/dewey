from memory import Memory


def test_memory_retrieve_falls_back_to_recent_items(tmp_path):
    memory = Memory(db_path=str(tmp_path / "memory.db"))
    memory.store("Earlier note", "conversations")
    memory.store("Most recent note", "conversations")

    results = memory.retrieve("no-match-token", "conversations", limit=2)

    assert [item["content"] for item in results] == ["Most recent note", "Earlier note"]
    memory.close()


def test_memory_deduplicates_exact_entries(tmp_path):
    memory = Memory(db_path=str(tmp_path / "memory.db"))

    first_id = memory.store("same content", "teacher_profile", category="profile")
    second_id = memory.store("same content", "teacher_profile", category="profile")

    assert first_id == second_id
    assert len(memory.get_all("teacher_profile")) == 1
    memory.close()
