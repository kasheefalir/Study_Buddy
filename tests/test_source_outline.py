from app.rag.outline import build, navigation, spread


def test_outline_links_all_chunks_without_merging_repeated_headings():
    chunks = [{"id": i, "chapter": heading, "text": "text", "location": f"Page {i}"}
              for i, heading in enumerate(["Intro", "Trees", "Intro"])]
    outline = build(chunks)
    assert [s["chunk_ids"] for s in outline] == [[0], [1], [2]]
    assert len({s["section_id"] for s in outline}) == 3


def test_navigation_finds_late_sections_and_discloses_omissions():
    chunks = [{"id": i, "chapter": f"Chapter {i}"} for i in range(20)]
    chunks[-1]["chapter"] = "Logistic Regression"
    result = navigation(chunks, "Explain logistic regression")
    assert result["sections"][0]["first_chunk_id"] == 19
    assert result["matched_headings"]
    assert result["omitted_sections"] == 19
    assert navigation(chunks, "unknown topic")["sections"][-1]["first_chunk_id"] == 19


def test_outline_clean_variant_and_empty_input():
    assert build([{"id": 1, "variant": "full"}, {"id": 2, "variant": "clean"}])[0]["chunk_ids"] == [2]
    assert navigation([])["total_sections"] == 0
    assert spread(10, 3) == [0, 4, 9]


def test_summary_outline_stays_bounded_and_source_linked(tmp_path, monkeypatch):
    from app.agents.retrieval_context import document_view
    from app.agents.context_budget import estimate, data_message
    from app.rag import overview
    chunks = [{"id": i, "chapter": f"Chapter {i}", "text": "Source text " * 500,
               "location": f"Page {i}"} for i in range(20)]
    nodes = {str(i): {"heading": f"Chapter {i}", "chunk_ids": [i],
             "summary": "Important section detail. " * 5, "concepts": ["Idea"]} for i in range(20)}
    nodes["root"] = {"heading": "Book", "chunk_ids": list(range(20)),
                     "summary": "Compressed introduction.", "concepts": ["Main idea"]}
    monkeypatch.setattr(overview, "cached", lambda *args: {
        "status": "ready", "root": "root", "nodes": nodes, "chapter_roots": list(map(str, range(20)))})
    sources, strategy = document_view(tmp_path, {"id": "book", "name": "Book"}, chunks, 1000, outline_details=True)
    assert strategy == "outline_details"
    assert estimate([data_message("Reviewed session materials", sources)]) <= 1000
    assert "Other details are omitted" in sources[0]["text"]
    assert sources[-1]["covered_chunk_ids"] == [19]
    assert all(s["variant"] == "generated_summary" for s in sources)
