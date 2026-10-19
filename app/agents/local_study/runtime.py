"""Bounded offline Ollama runtime and sampled process memory instrumentation."""
import asyncio
import json
import os
import time

import httpx

from app.config import settings


class LocalRuntime:
    def __init__(self, model, context=4096, output=700):
        if model not in {"llama3.2:3b", "phi4-mini:latest"}:
            raise ValueError("This candidate only evaluates the two small local models")
        self.model, self.context, self.output = model, context, output
        self.calls = []

    async def exclusive(self):
        """Unload other resident models, never delete or download weights."""
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.get(settings.ollama_url + "/api/ps")
            response.raise_for_status()
            for item in response.json()["models"]:
                name = item["name"]
                if name not in {self.model, settings.embedding_model, settings.embedding_model + ":latest"}:
                    result = await client.post(settings.ollama_url + "/api/generate", json={"model": name, "keep_alive": 0})
                    result.raise_for_status()

    async def structured_plan(self, messages, schema):
        return await self.chat(messages, schema=schema)

    async def chat(self, messages, schema=None):
        # A conservative character bound reserves room for the completion.
        if sum(len(m["content"]) for m in messages) > 10000:
            raise ValueError("Candidate input exceeds bounded context budget")
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=180) as client:
            resident = await client.get(settings.ollama_url + "/api/ps")
            resident.raise_for_status()
            others = [m["name"] for m in resident.json()["models"] if m["name"] not in {
                self.model, settings.embedding_model, settings.embedding_model + ":latest"}]
            if others:
                raise RuntimeError("Another generation model became resident; stop concurrent app use during evaluation")
            payload = {"model": self.model, "messages": messages, "stream": False, "keep_alive": "5m",
                       "options": {"num_ctx": self.context, "num_predict": self.output, "temperature": 0.1}}
            if schema is not None:
                payload["format"] = schema
            response = await client.post(settings.ollama_url + "/api/chat", json=payload)
            response.raise_for_status()
            result = response.json()
        self.calls.append({"seconds": time.monotonic() - start,
                           **{k: result.get(k) for k in ("prompt_eval_count", "eval_count", "done_reason", "load_duration")}})
        if not result.get("done") or result.get("done_reason") == "length":
            raise ValueError("Model output did not finish within the output budget")
        return result["message"]["content"]


class MemorySampler:
    """Observed RSS/USS peaks, not model-file size or proof of an 8 GB fit."""
    def __init__(self):
        self.samples = []
        self.stop = False

    async def run(self):
        import psutil
        while not self.stop:
            rss, uss, count, inaccessible = 0, 0, 0, 0
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    command = " ".join(proc.info["cmdline"] or [])
                    name = (proc.info["name"] or "").lower()
                    if proc.pid != os.getpid() and not any(term in name for term in ("ollama", "llama-server")) and "uvicorn app.main:app" not in command:
                        continue
                    rss += proc.memory_info().rss
                    count += 1
                    try:
                        uss += proc.memory_full_info().uss
                    except (psutil.AccessDenied, AttributeError):
                        inaccessible += 1
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    inaccessible += 1
            vm = psutil.virtual_memory()
            self.samples.append({"time": time.monotonic(), "rss": rss, "uss": uss, "count": count,
                                 "inaccessible": inaccessible, "host_total": vm.total, "host_available": vm.available})
            await asyncio.sleep(0.25)

    def report(self, start=0):
        samples = [s for s in self.samples if s["time"] >= start]
        if not samples:
            return {"available": False}
        return {"available": True, "samples": len(samples),
                "peak_process_rss_bytes": max(s["rss"] for s in samples),
                "peak_process_uss_bytes": max(s["uss"] for s in samples),
                "max_inaccessible_processes": max(s["inaccessible"] for s in samples),
                "host_total_bytes": samples[-1]["host_total"],
                "minimum_host_available_bytes": min(s["host_available"] for s in samples),
                "scope": "evaluation Python, Ollama daemon/runners, and Study Buddy uvicorn; excludes browser and other apps",
                "caveat": "Sampled peak, not high-water allocation. RSS may double-count shared pages; USS excludes shared memory."}
