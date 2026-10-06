from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
import pytest

from app.rag.pdf_content import extract_pdf
from app.rag.library import process


def make_pdf(path, text=True, encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    if text:
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 200 Td (Regularization reduces overfitting.) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_blank_page(width=300, height=300)
    writer.add_outline_item("Regression", 0)
    if encrypted:
        writer.encrypt("secret")
    writer.write(path)


def test_pdf_pages_chapters_progress_and_original_preserved(tmp_path):
    path = tmp_path / "lesson.pdf"
    make_pdf(path)
    original = path.read_bytes()
    progress = []
    passages, details = extract_pdf(path, lambda done, total: progress.append((done, total)))
    assert passages[0]["page"] == 1 and "Regression" in passages[0]["location"]
    assert "overfitting" in passages[0]["text"]
    assert details["pages_without_text"] == [2] and progress[-1] == (2, 2)
    item = {"id": "e" * 32, "name": "Lesson", "filename": path.name, "kind": "pdf"}
    assert process(tmp_path, item)["status"] == "Ready"
    assert path.read_bytes() == original


def test_scanned_and_password_protected_pdfs_have_actionable_errors(tmp_path):
    path = tmp_path / "scan.pdf"
    make_pdf(path, text=False)
    with pytest.raises(ValueError, match="OCR"):
        extract_pdf(path)
    make_pdf(path, encrypted=True)
    with pytest.raises(ValueError, match="password"):
        extract_pdf(path)


def test_pdf_source_opens_inline(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, materials
    from app.rag.library import write_json
    path = tmp_path / "lesson.pdf"
    make_pdf(path)
    identifier = "a" * 32
    write_json(tmp_path / (identifier + ".json"), {"id": identifier, "kind": "pdf", "filename": path.name, "name": "Lesson.pdf"})
    monkeypatch.setattr(materials, "root", tmp_path)
    response = TestClient(main.app).get(f"/api/materials/{identifier}/view")
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")
