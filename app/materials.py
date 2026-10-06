"""Local material library; ingestion and retrieval are separate stages."""
import json
import asyncio
import shutil
from pathlib import Path
from typing import Literal
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.rag.library import process
from app.rag.classmate_facts import prepare_facts
from app.llm.ollama_client import OllamaClient
from app.rag.semantic import prepare_index
from app.rag import overview

router = APIRouter(prefix="/api/materials")
root = settings.data_dir / "documents"
root.mkdir(parents=True, exist_ok=True)
allowed = {".pdf", ".pptx", ".docx", ".txt", ".md"}
processing = set()


@router.post("/{identifier}/process")
async def process_material(identifier: str):
    _, item = record(identifier)
    if identifier in processing:
        raise HTTPException(409, "This material is already being processed.")
    processing.add(identifier)
    try:
        await overview.pause(root, identifier)
        result = await asyncio.to_thread(process, root, item)
        if result["status"] == "Ready":
            result = await prepare_index(root, result)
        if result["status"] == "Ready":
            result = await prepare_facts(root, result, OllamaClient(settings.ollama_url, settings.ollama_model, timeout=60))
            overview.start(root, identifier, OllamaClient(settings.ollama_url, settings.ollama_model))
        return result
    finally:
        processing.discard(identifier)


@router.get("/{identifier}/extraction")
async def extraction(identifier: str, view: Literal["all", "clean", "full"] = "all"):
    record(identifier)
    filename = {"all": "extracted.json", "clean": "clean_content.json", "full": "full_content.json"}[view]
    path = root / identifier / filename
    if not path.exists():
        raise HTTPException(404, "No extracted text is available yet.")
    return FileResponse(path, filename="extracted-text.json")


@router.get("/{identifier}/snapshot")
async def snapshot(identifier: str):
    record(identifier)
    path = root / identifier / "original.bin"
    if not path.exists():
        raise HTTPException(404, "No page snapshot is available.")
    return FileResponse(path, media_type="application/octet-stream", filename="original-page.html")


@router.get("/{identifier}/facts")
async def facts(identifier: str):
    _, item = record(identifier)
    path = root / identifier / "facts.json"
    if item["status"] != "Ready" or not path.exists():
        return {"documentId": identifier, "facts": []}
    return json.loads(path.read_text())


def record(identifier):
    if len(identifier) != 32 or any(c not in "0123456789abcdef" for c in identifier):
        raise HTTPException(404, "Material not found")
    path = root / (identifier + ".json")
    if not path.exists():
        raise HTTPException(404, "Material not found")
    return path, json.loads(path.read_text())


@router.get("")
async def list_materials():
    return [import_state(json.loads(path.read_text())) for path in sorted(root.glob("*.json"))]


def import_state(item):
    item = dict(item)
    active = item["id"] in processing
    item["importing"] = active
    item["overview"] = overview.status(root, item["id"])
    if active:
        item["import_stage"] = "embedding" if item.get("import_stage") == "embedding" else "facts" if item.get("status") == "Ready" else item.get("import_stage", "extracting")
    elif item.get("status") == "Ready":
        item["import_stage"] = "ready"
    elif item.get("status") == "Processing":
        item["import_stage"] = "interrupted"
    elif item.get("error"):
        item["import_stage"] = "failed"
    else:
        item["import_stage"] = "stored"
    return item


@router.post("/{identifier}/overview", status_code=202)
async def prepare_overview(identifier: str):
    _, item = record(identifier)
    if item.get("status") != "Ready" or identifier in processing:
        raise HTTPException(409, "Finish importing this material first.")
    overview.start(root, identifier, OllamaClient(settings.ollama_url, settings.ollama_model))
    return {"status": "queued"}


@router.post("/{identifier}/overview/pause")
async def pause_overview(identifier: str):
    record(identifier)
    await overview.pause(root, identifier)
    return overview.status(root, identifier)


@router.post("/upload", status_code=201)
async def upload(request: Request, name: str):
    name = Path(name.replace("\\", "/")).name
    suffix = Path(name).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, "Choose a PDF, PPTX, DOCX, TXT, or Markdown file.")
    identifier = uuid4().hex
    path = root / (identifier + suffix)
    size = 0
    try:
        with path.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 25 * 1024 * 1024:
                    raise HTTPException(413, "Maximum file size is 25 MB.")
                handle.write(chunk)
        if not size:
            raise HTTPException(400, "The file is empty.")
        item = {"id": identifier, "name": name, "kind": suffix[1:], "size": size,
                "status": "Saved locally · not indexed", "filename": path.name}
        (root / (identifier + ".json")).write_text(json.dumps(item))
        return item
    except BaseException:
        path.unlink(missing_ok=True)
        raise


class Link(BaseModel):
    url: str = Field(max_length=2048)


@router.post("/url", status_code=201)
async def save_url(link: Link):
    parsed = urlsplit(link.url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(400, "Enter a valid http or https URL without credentials.")
    identifier = uuid4().hex
    item = {"id": identifier, "name": link.url, "url": link.url, "kind": "url",
            "status": "Link saved · not imported"}
    (root / (identifier + ".json")).write_text(json.dumps(item))
    return item


@router.get("/{identifier}/download")
async def download(identifier: str):
    _, item = record(identifier)
    if "filename" not in item:
        raise HTTPException(400, "This material is a link.")
    return FileResponse(root / item["filename"], filename=item["name"])


@router.get("/{identifier}/view")
async def view_pdf(identifier: str):
    _, item = record(identifier)
    if item.get("kind") != "pdf":
        raise HTTPException(400, "Page preview is available for PDFs only.")
    return FileResponse(root / item["filename"], filename=item["name"],
                        media_type="application/pdf", content_disposition_type="inline")


@router.delete("/{identifier}", status_code=204)
async def delete_material(identifier: str):
    if identifier in processing:
        raise HTTPException(409, "Wait for processing to finish before removing this material.")
    path, item = record(identifier)
    await overview.pause(root, identifier)
    if "filename" in item:
        (root / item["filename"]).unlink(missing_ok=True)
    path.unlink()
    archive = root / identifier
    if archive.exists():
        shutil.rmtree(archive)
