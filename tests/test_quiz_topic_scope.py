from app.agents.quiz import windows, coverage_windows


def test_named_chapter_beats_mentions_and_other_regression_topics():
    chunks = [
        {"id": 0, "text": "We cover logistic regression.", "chapter": "Introduction"},
        {"id": 1, "text": "CHAPTER 1\nLinear Regression\nregression", "chapter": "The Model"},
        {"id": 2, "text": "CHAPTER 2\nLogistic Regression\nlogistic regression", "chapter": "The Problem"},
        {"id": 3, "text": "The logistic function maps to probabilities.", "chapter": "The Logistic Function"},
        {"id": 4, "text": "Evaluate regression precision and recall.", "chapter": "Goodness of Fit"},
        {"id": 5, "text": "CHAPTER 3\nDecision Trees\nAnother regression model", "chapter": "Trees"},
    ]
    result = windows([({"id": "book"}, chunks)], "logistic regression")
    assert {i for w in result for i in w["chunk_ids"]} == {2, 3, 4}
    assert windows([({"id": "book"}, chunks)], "")


def test_concept_projection_cannot_attach_unrelated_source_window(monkeypatch, tmp_path):
    from app.rag import overview
    chunks = [{"id": 1, "text": "Logistic regression", "chapter": "Logistic Regression"},
              {"id": 2, "text": "Regression precision", "chapter": "Goodness of Fit"}]
    monkeypatch.setattr(overview, "concept_windows", lambda *args: [
        {"document_id": "book", "chunk_ids": [999], "concept": "Unrelated concept"}])
    result = coverage_windows(tmp_path, [({"id": "book"}, chunks)], "logistic regression")
    assert result and all("concept" not in w for w in result)


def test_reference_list_is_not_a_quiz_explanation_window():
    chunks = [{"id": 1, "text": "CHAPTER 2\nLogistic Regression\nProbabilities range from zero to one.",
               "chapter": "The Logistic Function"},
              {"id": 2, "text": "Logistic regression libraries: see scikit-learn.", "chapter": "For Further Investigation"}]
    result = windows([({"id": "book"}, chunks)], "logistic regression")
    assert {i for w in result for i in w["chunk_ids"]} == {1}
