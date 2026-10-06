import json
from uuid import uuid4

import pytest

from app.storage.conversation_store import ConversationStore


def test_save_preserves_full_session(tmp_path):
    store = ConversationStore(tmp_path, max_messages=2)
    conversation_id = str(uuid4())
    messages = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
    ]

    store.save(conversation_id, messages)

    assert store.load(conversation_id) == messages
    payload = json.loads((tmp_path / f"{conversation_id}.json").read_text())
    assert payload["id"] == conversation_id


def test_sessions_and_notes_survive_new_messages(tmp_path):
    store = ConversationStore(tmp_path)
    identifier = store.create_id()
    messages = [{"role": "user", "content": "Review biology"}]
    store.save(identifier, messages, memory="Preparing for a biology exam")
    store.save(identifier, messages + [{"role": "assistant", "content": "Let's begin."}])
    assert store.memory(identifier) == "Preparing for a biology exam"
    assert store.list_sessions()[0]["title"] == "Study session"
    assert store.list_sessions()[0]["message_count"] == 2
    (tmp_path / "broken.json").write_text("{")
    assert len(store.list_sessions()) == 1


def test_rejects_unsafe_conversation_id(tmp_path):
    store = ConversationStore(tmp_path)
    with pytest.raises(ValueError, match="Invalid conversation ID"):
        store.load("../../notes")
