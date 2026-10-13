from __future__ import annotations

import json
import re
import logging

from app.llm.ollama_client import OllamaClient
from app.storage.conversation_store import ConversationStore, Message
from app.rag.library import ground
from app.llm.usage import track_usage, usage_stage, summarize
from app.agents.tasks import PROMPTS, task_for, task_prompt
from app.agents.study_tools import review_materials, structured, IntentRoute, IntentDecision
from app.agents.quiz import quiz_turn, public_question, selected_option, REVIEW, START, NEXT, CHANGE
from app.agents.context_budget import pack, compress
from app.agents.reflection import reflect
from app.agents.grounded_answer import answer_from_sources
from app.agents.retrieval_context import current_study_session, reusable_evidence
from app.config import settings
from pathlib import Path

MISSING_EVIDENCE = "I couldn't retrieve supporting passages for that request. I can't answer it from the selected material yet; this doesn't mean the information isn't in the material."

ROUTER_PROMPT = (Path(__file__).parent / "prompts" / "intent_router.md").read_text(encoding="utf-8")
INTENT_RESOLUTION_PROMPT = (Path(__file__).parent / "prompts" / "intent_resolution.md").read_text(encoding="utf-8")
RETRIEVAL_PLAN_PROMPT = (Path(__file__).parent / "prompts" / "retrieval_plan.md").read_text(encoding="utf-8")


SYSTEM_PROMPT = (PROMPTS / "professor.md").read_text(encoding="utf-8")


def quiz_state(message, previous):
    # "Stop the quiz and review my misses" still needs the completed ledger.
    if re.search(r"\b(stop|end|exit|cancel)\b.*\bquiz\b", message, re.I) and not REVIEW.search(message):
        return {}
    if START.search(message) and not (previous.get("version") and CHANGE.search(message) and not re.search(r"\b(new|another|restart)\b", message, re.I)):
        return {"active": True, "topic": message[:500], "pending_question": "", "turns": 0}
    return dict(previous)


def needs_reference(message, quiz):
    if re.search(r"\b(slides?|power\s?point|pptx?|document|material|notes|file|according to|source)\b", message, re.I):
        return True
    return not quiz.get("active") and bool(re.search(r"\b(summarize|summarise|summary)\b", message, re.I))


class ChatAgent:
    def __init__(self, llm: OllamaClient, conversations: ConversationStore) -> None:
        self.llm = llm
        self.conversations = conversations

    async def reply(self, message: str, conversation_id: str | None = None, document_id: str = "", materials_root=None,
                    task: str = "auto", document_ids=None, quiz_question_id: str | None = None,
                    next_question_id: str | None = None) -> tuple[str, str]:
        with track_usage() as calls:
            return await self._reply(message, conversation_id, document_id, materials_root, calls, task, document_ids,
                                     quiz_question_id, next_question_id)

    async def _reply(self, message, conversation_id, document_id, materials_root, calls, task, document_ids,
                     quiz_question_id=None, next_question_id=None):
        active_id = conversation_id or self.conversations.create_id()
        session_document_ids = list(document_ids) if document_ids is not None else None
        history = self.conversations.load(active_id)
        notes = self.conversations.memory(active_id)
        summary_state = self.conversations.summary(active_id)
        saved_quiz = self.conversations.quiz(active_id)
        quiz = dict(saved_quiz) if materials_root is not None else quiz_state(message, saved_quiz)
        mode = (task if task != "auto" else "chat") if materials_root is not None else task_for(message, task, quiz)
        review_request = bool(REVIEW.search(message)) if materials_root is None else False
        # A click on a rendered choice is an explicit quiz event. Do not let a
        # conversational intent pass reinterpret it as a new free-form request.
        # Typed A-D answers receive the same treatment when they match the
        # pending options, while ordinary questions during review remain chat.
        explicit_quiz_answer = bool(quiz_question_id) or (
            quiz.get("active") and not quiz.get("paused") and selected_option(message, quiz) is not None)
        if explicit_quiz_answer:
            mode = "quiz"
        route = None
        if next_question_id:
            if quiz.get("question_id") != next_question_id or quiz.get("phase") not in {"review", "complete"}:
                raise ValueError("Quiz progress has changed. Refresh the session before advancing.")
            mode = "quiz"
            route = {"route": "quiz", "mode": "quiz", "activity_action": "next", "pause_activity": False}
            quiz.update(active=quiz.get("phase") != "complete", paused=False)
        reusable = reusable_evidence(materials_root, document_ids, history) if materials_root and document_ids else []
        last_material_request = next((m.get("material_review", {}).get("resolved_request")
            for m in reversed(history) if m.get("material_review", {}).get("resolved_request")), "")
        study_session = current_study_session(materials_root, document_ids or []) if materials_root and document_ids else {}
        # Natural-language turns have one intent owner. Choice clicks bypass it.
        if materials_root is not None and not explicit_quiz_answer and not next_question_id:
            inventory = []
            if document_ids:
                for identifier in document_ids:
                    try:
                        item = json.loads((materials_root / (identifier + ".json")).read_text())
                        inventory.append({"id": identifier, "title": item.get("page_title") or item.get("name", ""),
                                          "kind": item.get("kind", "file"), "url": item.get("url", "")[:160]})
                    except (OSError, ValueError, TypeError):
                        continue
            try:
                route = await structured(self.llm, "intent route", ROUTER_PROMPT,
                    {"latest_message": message[:1500],
                     "last_material_request": last_material_request[:1000],
                     "recent_dialogue": [{"role": m["role"], "content": m["content"][:350]} for m in history[-3:]],
                     "selected_materials": inventory,
                     "unfinished_activity": {"mode": mode, "quiz_active": bool(quiz.get("active")),
                                         "quiz_paused": bool(quiz.get("paused")), "phase": quiz.get("phase", ""),
                                         "pending_question": quiz.get("pending_question", "")[:300]},
                     "explicit_task": task})
                mode = route.get("mode", "chat")
                if route["route"] in {"conversation", "clarify"}:
                    mode = "summary_conversation" if mode == "summary_conversation" else "chat"
                elif route["route"] == "quiz":
                    mode = "quiz"
                elif mode not in {"summary_material", "simplify"}:
                    mode = "chat"
                if route["route"] == "retrieve":
                    decision = await structured(self.llm, "retrieval plan", RETRIEVAL_PLAN_PROMPT,
                        {"latest_message": message[:1500],
                         "last_material_request": last_material_request[:1000],
                         "recent_dialogue": [{"role": m["role"], "content": m["content"][:350]} for m in history[-3:]],
                         "selected_materials": inventory,
                         "intent": route,
                         "previous_evidence": [{"document_id": s["document_id"], "location": s.get("location", ""),
                                                "text": s["text"][:500]} for s in reusable[:6]],
                         "explicit_task": task})
                    route.update(query=decision["query"], reuse_evidence=decision["reuse_evidence"])
                    selected = set(document_ids or [])
                    resolved = [identifier for identifier in decision["document_ids"] if identifier in selected]
                    document_ids = resolved or document_ids
            except (AssertionError, AttributeError, KeyError, RuntimeError, TypeError, ValueError):
                # Planner failures cannot change the intent owner's decision.
                if route and route.get("route") == "conversation":
                    mode = "chat"
                elif not route:
                    route = {"route": "clarify", "query": "", "pause_activity": False}
                    mode = "chat"
            action = (route or {}).get("activity_action", "keep")
            review_request = action == "review"
            if action == "start" and route["route"] == "quiz":
                quiz = {}
            elif action == "end":
                quiz.update(active=False, paused=False)
            elif action in {"resume", "next"} and route["route"] == "quiz":
                quiz.update(active=quiz.get("phase") != "complete", paused=False)
            if route and (route["pause_activity"] or action == "pause") and mode != "quiz":
                quiz["paused"] = True
                quiz["active"] = False
        if mode == "quiz" and not quiz.get("active") and not quiz.get("version") and not REVIEW.search(message):
            quiz = {"active": True, "topic": message[:500], "pending_question": "", "turns": 0}
        if (document_ids is not None or review_request) and mode == "quiz" and (review_request or not route or route["route"] == "quiz"):
            response, quiz, sources = await quiz_turn(materials_root, document_ids or [], message, quiz, self.llm, history,
                **({"activity_action": route.get("activity_action", "keep")} if route else {}))
            if response is not None:
                question_ui = public_question(quiz)
                previous_question = self.conversations.quiz(active_id).get("question_id")
                if question_ui.get("answered"):
                    for entry in history:
                        if entry.get("quiz_question", {}).get("id") == question_ui["id"]:
                            entry["quiz_question"] = question_ui
                show_question = question_ui and question_ui["id"] != previous_question
                user_entry = {"role": "user", "content": message}
                if quiz_question_id:
                    user_entry["quiz_selection_for"] = quiz_question_id
                updated = [*history, user_entry,
                           {"role": "assistant", "content": response, "sources": sources, "usage": summarize(calls),
                            **({"quiz_question": question_ui} if show_question else {})}]
                self.conversations.save(active_id, updated, document_ids=session_document_ids, quiz=quiz)
                return active_id, response
            if explicit_quiz_answer:
                return active_id, "That question has already been answered. Choose Next question, or ask about this one."
            mode = "chat"
        prompt = SYSTEM_PROMPT + "\nCurrent activity:\n" + task_prompt(mode)
        if route and route["route"] in {"conversation", "clarify"}:
            prompt += "\nThis turn is conversational, not a continuation of material analysis. Answer the latest message naturally. Selected materials are background awareness, not a request to teach them. Do not resume a previous task unless the student requests it."
        context = {}
        if study_session:
            context["study_session"] = study_session
        # Older student intent is kept as bounded excerpts, not a generated summary.
        older = history[:-self.conversations.max_messages]
        questions = [m["content"][:300] for m in older if m["role"] == "user"]
        if questions:
            context["earlier_student_messages"] = questions[:2] + questions[-6:] if len(questions) > 8 else questions
        if quiz.get("active"):
            context["quiz"] = {key: value for key, value in quiz.items()
                               if key not in {"prepared_questions", "window_plan", "window_reviews"}}
        if quiz.get("version"):
            # The saved quiz ledger, unlike prior prose, is the source of truth
            # for any conversational follow-up about correctness or misses.
            context["quiz_progress"] = {
                "instruction": "These saved quiz results are authoritative. Do not call a question correct or missed unless this ledger says so.",
                "phase": quiz.get("phase", ""),
                "pending_question": quiz.get("pending_question", "")[:500],
                "results": [{"number": result.get("number"), "question": result.get("question", "")[:280],
                             "verdict": result.get("verdict"), "student_answer": result.get("student_answer", "")[:180]}
                            for result in quiz.get("results", [])[-12:]],
            }
        if notes:
            context["saved_study_notes"] = notes
        if summary_state.get("text"):
            context["conversation_summary"] = summary_state["text"]
        sources = []
        review_context = {}
        evidence_required = bool(route and route["route"] == "retrieve") or mode == "summary_material"
        retrieval_question = (route.get("query") or message) if route else message
        if route and route["route"] == "retrieve" and route.get("reuse_evidence") and reusable and all(
                s["document_id"] in (document_ids or []) for s in reusable):
            sources = reusable
            review_context.update(approach="source_focused", resolved_request=retrieval_question,
                                  selected_document_ids=list(document_ids), evidence_reused=True)
            context["material_review"] = dict(review_context)
        if document_ids and mode != "summary_conversation" and (not route or route["route"] == "retrieve"):
            sources = sources or await review_materials(materials_root, document_ids, retrieval_question,
                [{"role": m["role"], "content": m["content"][:1000],
                  "previous_source_ids": m.get("material_review", {}).get("selected_document_ids", [])} for m in history[-4:]],
                self.llm, overview=mode == "summary_material", review_context=review_context,
                conversation_context={"summary": summary_state.get("text", "")[:2000], "study_notes": notes[:1000]})
            evidence_required = evidence_required or review_context.get("approach") == "source_focused"
            if evidence_required and not sources:
                first_attempt = dict(review_context)
                sources = await review_materials(materials_root, document_ids, retrieval_question,
                    [{"role": m["role"], "content": m["content"][:1000]} for m in history[-4:]],
                    self.llm, overview=mode == "summary_material", review_context=review_context,
                    feedback="The resolved request requires source evidence, but the first attempt returned no passages. Refine the query or choose a different reading tool within the selected materials. Do not substitute general knowledge. If the source is genuinely unclear, choose clarify.")
                review_context["empty_evidence_retry"] = {"first_attempt": first_attempt, "recovered": bool(sources)}
            context["material_review"] = {"available_materials": review_context.get("available_materials", []),
                "selected_document_ids": review_context.get("selected_document_ids", []),
                "approach": review_context.get("approach", ""), "coverage": review_context.get("coverage", []),
                "resolved_request": retrieval_question}
            review_context["resolved_request"] = retrieval_question
        elif document_ids is None and document_id and mode != "summary_conversation" and (not route or route["route"] == "retrieve") and (mode == "summary_material" or needs_reference(message, quiz)):
            evidence_required = True
            follow_up = [{"role": m["role"], "content": m["content"][:1200]} for m in history[-4:]]
            with usage_stage("study planning"):
                sources = await ground(materials_root, document_id, json.dumps({"question": message, "recent_conversation": follow_up}), self.llm)
        source_focused = evidence_required or review_context.get("approach") == "source_focused"
        if sources:
            prompt = (PROMPTS / "grounded_answer.md").read_text(encoding="utf-8") + "\n" + task_prompt(mode)
        draft_history = history
        if source_focused:
            # Preserve original transcript offsets and student intent, not unverified assistant facts.
            draft_history = [m if m["role"] == "user" else {"role": "assistant", "content":
                "[Earlier answer withheld as evidence; follow-up intent is in resolved_request.]"} for m in history]
            context.pop("conversation_summary", None)
            context.pop("saved_study_notes", None)
        messages, packed_sources, budget = pack(prompt, message, draft_history, context, sources, self.conversations.max_messages)
        newly_omitted = budget["history_start"] - summary_state.get("through", 0)
        if not source_focused and (newly_omitted >= 8 or (newly_omitted > 0 and budget["recent_messages"] < min(len(history), self.conversations.max_messages))):
            try:
                summary_state = await compress(self.llm, history, summary_state, budget["history_start"])
                if summary_state.get("text"):
                    context["conversation_summary"] = summary_state["text"]
            except (RuntimeError, ValueError):
                logging.getLogger(__name__).warning("Conversation summary unavailable; retaining saved summary and recent context")
            messages, packed_sources, budget = pack(prompt, message, history, context, sources, self.conversations.max_messages)
        budget["summarized_messages"] = summary_state.get("through", 0)
        sources = packed_sources
        missing_evidence = evidence_required and not sources
        if missing_evidence:
            response = MISSING_EVIDENCE
        elif sources:
            response = await answer_from_sources(self.llm, messages, sources, resolved_request=retrieval_question)
        else:
            response = await self.llm.chat(messages)
        async def retrieve_again(feedback):
            recovered = await review_materials(materials_root, document_ids or [document_id], message,
                [{"role": m["role"], "content": m["content"][:1000]} for m in history[-4:]],
                self.llm, overview=mode == "summary_material", review_context=review_context,
                feedback=feedback)
            context["material_review"] = {"available_materials": review_context.get("available_materials", []),
                "selected_document_ids": review_context.get("selected_document_ids", []),
                "approach": review_context.get("approach", ""), "coverage": review_context.get("coverage", [])}
            return recovered
        reflection = {"status": "disabled", "reviews": []}
        if settings.response_review_enabled and not evidence_required and not sources:
            response, sources, reflection = await reflect(self.llm, message, response, prompt,
                draft_history, context, sources, self.conversations.max_messages,
                retrieve=retrieve_again if (document_ids or document_id) and mode != "summary_conversation" else None)
        if mode == "quiz" and quiz.get("active") and not quiz.get("version") and not quiz.get("topics"):
            quiz["turns"] = quiz.get("turns", 0) + 1
            if "?" in response and not re.search(r"\bhint\b", message, re.I):
                quiz["pending_question"] = response[-2000:]
        user_entry: Message = {"role": "user", "content": message}
        if quiz_question_id:
            user_entry["quiz_selection_for"] = quiz_question_id
        updated: list[Message] = [*history, user_entry,
                                 {"role": "assistant", "content": response, "sources": sources, "material_review": review_context,
                                  "reflection": reflection,
                                  "usage": {**summarize(calls), "context": budget}}]
        self.conversations.save(active_id, updated, document_id=document_id, document_ids=session_document_ids, quiz=quiz, summary=summary_state)
        return active_id, response
