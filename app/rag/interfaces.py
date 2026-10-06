from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    text: str
    document_id: str
    source_name: str
    location: str | None
    score: float


class MaterialSearcher(Protocol):
    def search(self, query: str, document_id: str | None = None, limit: int = 5) -> list[SearchResult]: ...
