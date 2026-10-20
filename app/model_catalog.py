"""Ollama discovery and explicitly requested recommended-model downloads."""
import asyncio
import json

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api/models")
RECOMMENDED = ("llama3.2:3b", "phi4-mini:latest", "gpt-oss:20b", "gemma4:31b-cloud")
download = {"active": False}
download_task = None


class DownloadRequest(BaseModel):
    model: str


@router.get("")
async def catalog():
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{settings.ollama_url}/api/tags")
            response.raise_for_status()
            models = []
            unavailable = []
            for item in response.json().get("models", []):
                name = item.get("name", "")
                try:
                    info = await client.post(f"{settings.ollama_url}/api/show", json={"model": name})
                    info.raise_for_status()
                    capabilities = info.json().get("capabilities", [])
                except (httpx.HTTPError, ValueError):
                    unavailable.append(name)
                    continue
                if "completion" in capabilities:
                    models.append({"name": name, "size": item.get("size", 0)})
        return {"models": models, "unavailable": unavailable,
                "recommended": RECOMMENDED, "download": dict(download)}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Cannot discover models. Open or update Ollama and try again.") from exc


async def pull(model):
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as client:
            async with client.stream("POST", f"{settings.ollama_url}/api/pull",
                                     json={"model": model, "stream": True}) as response:
                response.raise_for_status()
                success = False
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("error"):
                        raise ValueError(event["error"])
                    download.update(status=event.get("status", "Downloading"),
                                    completed=event.get("completed", 0), total=event.get("total", 0))
                    success = event.get("status") == "success"
                if not success:
                    raise ValueError("Download ended before completion. Try again.")
    except (httpx.HTTPError, ValueError) as exc:
        download.update(status="Download failed. Check Ollama and retry.", error=str(exc))
    finally:
        download["active"] = False


@router.post("/download", status_code=202)
async def start_download(request: DownloadRequest):
    global download_task
    if request.model not in RECOMMENDED:
        raise HTTPException(400, "Only recommended models can be downloaded here.")
    if download["active"]:
        raise HTTPException(409, "A model download is already running.")
    download.clear()
    download.update(active=True, model=request.model, status="Starting download")
    download_task = asyncio.create_task(pull(request.model))
    return dict(download)


@router.get("/download")
async def download_status():
    return dict(download)
