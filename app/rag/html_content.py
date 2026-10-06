"""Two recoverable views of a webpage, grouped by headings."""
from bs4 import BeautifulSoup, NavigableString, Comment
import trafilatura


def sections(markup, url, variant):
    soup = BeautifulSoup(markup, "html.parser")
    for node in soup(["script", "style", "noscript", "template"]):
        node.decompose()
    heading, lines, result = "Page text", [], []

    def flush():
        if lines:
            result.append({"location": heading, "text": "\n".join(lines), "url": url, "variant": variant})
            lines.clear()

    for node in (soup.body or soup).descendants:
        if getattr(node, "name", None) in {"h1", "h2", "h3", "h4", "h5", "h6", "head"}:
            # Trafilatura XML uses <head> for section headings.
            if node.name == "head" and variant == "full":
                continue
            flush()
            heading = node.get_text(" ", strip=True) or "Page text"
        elif isinstance(node, NavigableString) and not isinstance(node, Comment):
            text = str(node).strip()
            if text:
                lines.append(text)
    flush()
    return result


def extract_versions(raw, url):
    soup = BeautifulSoup(raw, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    full = sections(str(soup), url, "full")
    try:
        xml = trafilatura.extract(raw, url=url, output_format="xml", include_tables=True,
                                  include_comments=False, include_formatting=True)
        # Only the main content; XML metadata remains represented by the source URL/title.
        body = BeautifulSoup(xml or "", "xml").find("main")
        clean = sections(str(body), url, "clean") if body else []
    except Exception:
        clean = []
    return title, clean, full
