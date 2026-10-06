from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict, NotRequired
from uuid import UUID, uuid4


class Message(TypedDict):
    role: str
    content: str
    sources: NotRequired[list[dict]]
    usage: NotRequired[dict]
    material_review: NotRequired[dict]
    reflection: NotRequired[dict]
    quiz_question: NotRequired[dict]
    quiz_selection_for: NotRequired[str]


class ConversationStore:
    def __init__(self, directory: Path, max_messages: int = 16) -> None:
        self.directory = directory
        self.max_messages = max_messages
        self.directory.mkdir(parents=True, exist_ok=True)

    def create_id(self) -> str:
        return str(uuid4())

    def load(self, conversation_id: str) -> list[Message]:
        path = self._path(conversation_id)
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        messages = payload.get("messages", [])
        return [item for item in messages if item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str)]

    def memory(self, conversation_id: str) -> str:
        path = self._path(conversation_id)
        if not path.exists():
            return ""
        return json.loads(path.read_text(encoding="utf-8")).get("memory", "")

    def document(self, conversation_id: str) -> str:
        path = self._path(conversation_id)
        return json.loads(path.read_text()).get("document_id", "") if path.exists() else ""

    def documents(self, conversation_id: str) -> list[str]:
        path = self._path(conversation_id)
        data = json.loads(path.read_text()) if path.exists() else {}
        return data.get("document_ids", [data["document_id"]] if data.get("document_id") else [])

    def session_title(self, payload: dict, materials_root: Path | None = None) -> str:
        explicit = payload.get("title", "").strip()
        if explicit and explicit != "Study session":
            return explicit[:100]
        ids = payload.get("document_ids", [payload["document_id"]] if payload.get("document_id") else [])
        names = []
        for identifier in ids:
            if materials_root is None or not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
                continue
            try:
                item = json.loads((materials_root / (identifier + ".json")).read_text())
                name = item.get("page_title") or item.get("name", "")
                if item.get("kind") != "url":
                    name = Path(name).stem
                if name:
                    names.append(name.replace("_", " "))
            except (OSError, ValueError):
                continue
        if not names:
            return "Study session"
        suffix = f" + {len(names) - 1} more" if len(names) > 1 else ""
        return names[0][:100 - len(suffix)] + suffix

    def delete(self, conversation_id: str) -> None:
        self._path(conversation_id).unlink()

    def list_sessions(self, materials_root: Path | None = None) -> list[dict]:
        sessions = []
        for path in self.directory.glob("*.json"):
            try:
                identifier = str(UUID(path.stem))
                payload = json.loads(path.read_text(encoding="utf-8"))
                messages = self.load(identifier)
                title = self.session_title(payload, materials_root)
                sessions.append({"id": identifier, "title": title[:100],
                                 "updated_at": payload.get("updated_at", ""),
                                 "message_count": len(messages), "document_ids": self.documents(identifier)})
            except (ValueError, TypeError, KeyError, AttributeError):
                continue
        return sorted(sessions, key=lambda item: item["updated_at"], reverse=True)

    def quiz(self, conversation_id: str) -> dict:
        path = self._path(conversation_id)
        return json.loads(path.read_text()).get("quiz", {}) if path.exists() else {}

    def summary(self, conversation_id: str) -> dict:
        path = self._path(conversation_id)
        return json.loads(path.read_text()).get("summary", {}) if path.exists() else {}

    def save(self, conversation_id: str, messages: list[Message], memory: str | None = None, document_id: str | None = None, quiz: dict | None = None, document_ids: list[str] | None = None, title: str | None = None, summary: dict | None = None) -> None:
        path = self._path(conversation_id)
        previous = json.loads(path.read_text()) if path.exists() else {}
        ids = list(dict.fromkeys(document_ids)) if document_ids is not None else ([document_id] if document_id else []) if document_id is not None else self.documents(conversation_id)
        payload = {
            "id": conversation_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": messages,
            "memory": self.memory(conversation_id) if memory is None else memory,
            "document_id": ids[0] if ids else "",
            "document_ids": ids,
            "title": previous.get("title", "") if title is None else title,
            "quiz": self.quiz(conversation_id) if quiz is None else quiz,
            "summary": previous.get("summary", {}) if summary is None else summary,
        }
        fd, temporary_name = tempfile.mkstemp(dir=self.directory, prefix=".conversation-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(temporary_name, path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def _path(self, conversation_id: str) -> Path:
        try:
            normalized_id = str(UUID(conversation_id))
        except ValueError as exc:
            raise ValueError("Invalid conversation ID") from exc
        return self.directory / f"{normalized_id}.json"
