"""Page-preserving text extraction. Scanned images require a separate OCR path."""
from pypdf import PdfReader


def extract_pdf(path, progress=None):
    reader = PdfReader(path, strict=False)
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("This PDF is password protected. Upload an unlocked copy.")
    total = len(reader.pages)
    if total > 2000:
        raise ValueError("This PDF exceeds 2,000 pages. Import individual chapters.")
    headings = []

    def outline(entries):
        for entry in entries:
            if isinstance(entry, list):
                outline(entry)
            else:
                try:
                    page = reader.get_destination_page_number(entry)
                    if page is not None and page >= 0:
                        headings.append((page, str(entry.title)[:160]))
                except (ValueError, KeyError, AttributeError):
                    continue
    try:
        outline(reader.outline)
    except Exception:
        pass  # A damaged outline must not prevent extraction of readable pages.
    headings.sort(key=lambda entry: entry[0])
    result, empty, failed, characters = [], [], [], 0
    chapter, next_heading = "", 0
    for index, page in enumerate(reader.pages):
        while next_heading < len(headings) and headings[next_heading][0] <= index:
            chapter = headings[next_heading][1]
            next_heading += 1
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
            failed.append(index + 1)
        if text:
            characters += len(text)
            if characters > 10_000_000:
                raise ValueError("Extracted PDF text exceeds the import limit. Import individual chapters.")
            result.append({"location": f"Page {index + 1}" + (f" · {chapter}" if chapter else ""),
                           "page": index + 1, "chapter": chapter, "text": text})
        else:
            empty.append(index + 1)
        if progress and (index % 5 == 0 or index + 1 == total):
            progress(index + 1, total)
    if not result:
        raise ValueError("No readable PDF text found. This file may need OCR; scanned images are not supported yet.")
    return result, {"page_count": total, "text_pages": len(result), "pages_without_text": empty,
                    "failed_pages": failed, "outline_sections": len(headings)}
