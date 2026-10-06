from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agents.chat_agent import ChatAgent
from app.agents import activity
from app.config import settings
from app.materials import router as materials_router
from app import materials
from app.llm.ollama_client import OllamaClient, OllamaError
from app.storage.conversation_store import ConversationStore, Message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Local AI Study Buddy", version="0.1.0")
app.include_router(materials_router)
llm = OllamaClient(settings.ollama_url, settings.ollama_model, settings.request_timeout_seconds)
store = ConversationStore(settings.conversations_dir, settings.max_history_messages)
agent = ChatAgent(llm, store)
static_dir = Path(__file__).parent / "ui" / "static"
tileset_dir = Path(__file__).parents[1] / "2D Pixel Top-Down Japanese School Tileset"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/tileset", StaticFiles(directory=tileset_dir), name="tileset")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12_000)
    conversation_id: str | None = None
    document_id: str = ""
    document_ids: list[str] | None = Field(default=None, max_length=12)
    task: Literal["auto", "chat", "quiz", "simplify", "summary_conversation", "summary_material"] = "auto"
    quiz_question_id: str | None = Field(default=None, max_length=32)


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    sources: list[dict] = []
    usage: dict = {}
    quiz_question: dict = {}
    quiz_current: dict = {}


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: list[Message]
    memory: str = ""
    document_id: str = ""
    document_ids: list[str] = []
    quiz: dict = {}
    title: str = "Study session"


class MemoryRequest(BaseModel):
    memory: str = Field(max_length=4000)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {"app": "ok", "ollama": await llm.health()}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    active_id = request.conversation_id or store.create_id()
    if active_id in activity.active:
        raise HTTPException(409, "Professor is already responding in this session.")
    try:
        if request.conversation_id and not store._path(active_id).exists():
            raise HTTPException(404, "Study session not found. Start a new session.")
        if request.quiz_question_id:
            pending = store.quiz(active_id)
            if pending.get("question_id") != request.quiz_question_id or pending.get("phase") != "question" or not pending.get("active"):
                raise HTTPException(409, "This question is no longer awaiting an answer. Reopen the session to refresh it.")
        ids = request.document_ids
        if ids is None and request.conversation_id and not request.document_id:
            ids = store.documents(request.conversation_id)
        with activity.track(active_id):
            conversation_id, reply = await agent.reply(request.message.strip(), active_id, request.document_id, materials.root,
                                                       task=request.task, document_ids=ids,
                                                       quiz_question_id=request.quiz_question_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    answer = store.load(conversation_id)[-1]
    from app.agents.quiz import public_question
    return ChatResponse(conversation_id=conversation_id, message=reply, sources=answer.get("sources", []), usage=answer.get("usage", {}),
                        quiz_question=answer.get("quiz_question", {}), quiz_current=public_question(store.quiz(conversation_id)))


@app.get("/api/conversations/{identifier}/activity")
async def conversation_activity(identifier: str):
    return {"active": identifier in activity.active, "stage": activity.active.get(identifier, "")}


@app.get("/api/conversations")
async def sessions() -> list[dict]:
    return store.list_sessions(materials.root)


@app.delete("/api/conversations/{conversation_id}")
async def delete_session(conversation_id: str):
    if conversation_id in activity.active:
        raise HTTPException(409, "Wait for Professor's reply before deleting this session.")
    try:
        store.delete(conversation_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "Study session not found") from exc
    return {"deleted": True}


class SessionSetup(BaseModel):
    title: str = Field(default="Study session", min_length=1, max_length=100)
    document_ids: list[str] = Field(default_factory=list, max_length=12)


@app.post("/api/conversations", status_code=201)
async def create_session(request: SessionSetup):
    for identifier in request.document_ids:
        materials.record(identifier)
    identifier = store.create_id()
    store.save(identifier, [], title=request.title.strip(), document_ids=request.document_ids)
    return {"conversation_id": identifier}


@app.put("/api/conversations/{conversation_id}/materials")
async def session_materials(conversation_id: str, request: SessionSetup):
    try:
        if not store._path(conversation_id).exists():
            raise HTTPException(404, "Study session not found")
        for identifier in request.document_ids:
            materials.record(identifier)
        store.save(conversation_id, store.load(conversation_id), document_ids=request.document_ids,
                   quiz={})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    title = next(s["title"] for s in store.list_sessions(materials.root) if s["id"] == conversation_id)
    return {"document_ids": store.documents(conversation_id), "title": title}


@app.put("/api/conversations/{conversation_id}/memory")
async def save_memory(conversation_id: str, request: MemoryRequest) -> dict:
    try:
        messages = store.load(conversation_id)
        if not store._path(conversation_id).exists():
            raise HTTPException(status_code=404, detail="Study session not found")
        store.save(conversation_id, messages, memory=request.memory.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": True}


@app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def conversation(conversation_id: str) -> ConversationResponse:
    try:
        if not store._path(conversation_id).exists():
            raise HTTPException(404, "Study session not found")
        messages = store.load(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    quiz = store.quiz(conversation_id)
    progress = {key: quiz[key] for key in ("active", "cursor", "phase", "results", "total") if key in quiz}
    progress["concept_count"] = quiz.get("total", len(quiz.get("topics", [])))
    progress["reviewed_windows"] = len(quiz.get("window_reviews", []))
    progress["available_windows"] = quiz.get("available_windows", 0)
    from app.agents.quiz import public_question
    progress["current_question"] = public_question(quiz)
    title = next((s["title"] for s in store.list_sessions(materials.root) if s["id"] == conversation_id), "Study session")
    return ConversationResponse(conversation_id=conversation_id, messages=messages, memory=store.memory(conversation_id), document_id=store.document(conversation_id), document_ids=store.documents(conversation_id), quiz=progress, title=title)
