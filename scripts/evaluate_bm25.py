"""In-memory SQLite experiment, not a storage migration or production retriever."""
import json
import sqlite3
import time
from pathlib import Path

from app.config import settings
from app.agents.study_tools import library
from app.rag.library import tokens, candidates


def bm25_hits(chunks, query, limit=3):
    terms = list(dict.fromkeys(tokens(query)))
    if not terms:
        return []
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE VIRTUAL TABLE passages USING fts5(text)")
        db.executemany("INSERT INTO passages(rowid, text) VALUES (?, ?)",
                       [(c["id"], c["text"]) for c in chunks])
        match = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
        rows = db.execute("SELECT rowid FROM passages WHERE passages MATCH ? "
                          "ORDER BY bm25(passages), rowid LIMIT ?", (match, limit)).fetchall()
    by_id = {c["id"]: c for c in chunks}
    return [by_id[row[0]] for row in rows]


def main():
    _, chunks = library(settings.data_dir / "documents", ["3a4c66034f8a4b6cba7320b89e254ff5"])[0]
    rows = []
    for query, gold in [("degree centrality", 86), ("betweenness centrality measure", 675),
                        ("degree centrality number of friends", 86)]:
        start = time.monotonic()
        result = bm25_hits(chunks, query)
        ids = [c["id"] for c in result]
        lexical = [c["id"] for c in candidates(chunks, query, 3)]
        rows.append({"query": query, "bm25_ids": ids, "gold_hit": gold in ids,
                     "existing_lexical_ids": lexical, "existing_lexical_gold_hit": gold in lexical,
                     "seconds_including_index_build": round(time.monotonic() - start, 4)})
    path = Path("data/study-reviews/sqlite-bm25.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
