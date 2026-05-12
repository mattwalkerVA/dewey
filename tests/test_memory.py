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


def test_memory_delete_collection_only_removes_target_collection(tmp_path):
    memory = Memory(db_path=str(tmp_path / "memory.db"))
    memory.store("profile note", "teacher_profile", category="profile")
    memory.store("conversation note", "conversations")

    deleted = memory.delete_collection("teacher_profile")

    assert deleted == 1
    assert memory.get_all("teacher_profile") == []
    assert len(memory.get_all("conversations")) == 1
    memory.close()


def test_memory_delete_all_removes_everything(tmp_path):
    memory = Memory(db_path=str(tmp_path / "memory.db"))
    memory.store("profile note", "teacher_profile", category="profile")
    memory.store("conversation note", "conversations")

    deleted = memory.delete_all()

    assert deleted == 2
    assert memory.get_all("teacher_profile") == []
    assert memory.get_all("conversations") == []
    memory.close()
