"""Incremental, bounded quizzes. Saved windows are reviewed only as needed."""
from copy import deepcopy
from difflib import SequenceMatcher
from uuid import uuid4
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.context_budget import estimate, input_limit
from app.agents.study_tools import OUTPUTS, library, passages, structured, structured_messages
from app.rag.library import candidates


class QuizRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=50)
    focus: str = Field(default="", max_length=200)
    format: Literal["short_answer", "multiple_choice"] = "multiple_choice"
    guidelines: str = Field(default="", max_length=300)


class QuizIntent(BaseModel):
    action: Literal["answer", "change", "hint", "discuss"]
    format: Literal["short_answer", "multiple_choice"]
    guidelines: str = Field(max_length=300)
    acknowledgement: str = Field(max_length=200)
    count: int | None = Field(default=None, ge=1, le=50)
    focus: str | None = Field(default=None, max_length=200)


class ChoiceQuestion(BaseModel):
    summary: str = Field(min_length=1, max_length=400)
    question: str = Field(min_length=5, max_length=900)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_answer: str = Field(min_length=1, max_length=900, description="Exact text of the correct option, copied verbatim from options")
    expected_answer: str = Field(min_length=20, max_length=900)


class ChoiceQuality(BaseModel):
    valid: bool
    stem_answered: bool = Field(description="Whether the designated correct option directly answers the question as written.")
    distractors_answer_stem: bool = Field(description="Whether each distractor is a plausible answer to the same stem, even though it is wrong.")
    issue: str = Field(default="", max_length=500,
                       description="A concise, actionable reason the draft question should be regenerated.")


class WindowQuestion(BaseModel):
    summary: str = Field(min_length=1, max_length=400)
    question: str = Field(min_length=5, max_length=900,
                          description="Self-contained conceptual question, not a numerical calculation or source trivia")
    expected_answer: str = Field(min_length=20, max_length=900,
                                 description="Explain the conceptual reasoning in words, not a bare number")


class Assessment(BaseModel):
    verdict: Literal["correct", "incorrect", "uncertain", "hint"]
    explanation: str = Field(min_length=1, max_length=900)
    correction: str = Field(min_length=1, max_length=900)
    example: str = Field(min_length=1, max_length=900)


class ChoiceFeedback(BaseModel):
    explanation: str = Field(min_length=1, max_length=900,
                             description="Feedback about the answered question only. Do not ask a new question or suggest answer choices.")
    correction: str = Field(min_length=1, max_length=900,
                            description="Teaching correction for the answered question only, with no follow-up question.")
    example: str = Field(min_length=1, max_length=900,
                         description="Concrete example for the answered question only, with no follow-up question.")


OUTPUTS.update({"quiz request": QuizRequest, "quiz window": WindowQuestion, "quiz assessment": Assessment,
                "quiz intent": QuizIntent, "quiz choices": ChoiceQuestion, "choice quality": ChoiceQuality,
                "choice feedback": ChoiceFeedback})
CHANGE = re.compile(r"\b(?:make|change|switch|turn|convert|regenerate|instead|rather|prefer|want|give)\b.*\b(?:choice|options|questions?|quiz|harder|easier|format)\b|\b(?:multiple[ -]choice|harder|easier)\b", re.I)
REVIEW = re.compile(r"\b(?:review|revisit|show)\b.*\b(?:missed|wrong|incorrect|mistakes)\b", re.I)
NEXT = re.compile(r"\s*(?:next(?: question)?|continue|ready)[.!]?\s*", re.I)
START = re.compile(r"\b(?:quiz|test) me\b|\b(?:start|new|another|create|make|generate|give|get|want)\b.*\bquiz\b|\bask me\b.*\bquestions?\b", re.I)

WINDOW_PROMPT = (
    "Summarize the main teachable idea in this text window in 1-2 sentences, then create ONE "
    "self-contained question in the requested format and a private grading key. Follow the student's focus "
    "when it is supported. Test understanding, not page numbers, names, or incidental dataset "
    "statistics. Ask about the academic idea in your summary, never author jokes, rhetorical "
    "asides, stereotypes, or comparisons about who is smarter. Use neutral academic language. Ignore incidental "
    "statistics. Include any necessary context in the question, never its answer. Avoid "
    "questions about unexplained code identifiers. Ask about the underlying concept instead. "
    "Follow the student's guidelines and difficulty. Prefer conceptual reasoning unless calculations are requested. Do not repeat "
    "previous questions. Base the question on the supplied reference window. "
    "You may use subject knowledge to explain the source concepts, but do not invent source facts."
    " If no material is attached, use the requested subject and general knowledge."
)
WINDOW_PROMPT += "\n" + (Path(__file__).parent / "prompts" / "quiz.md").read_text()
GRADE_PROMPT = (
    "Assess the student's answer to the pending question using the reference and sound subject "
    "knowledge. The expected answer is a fallible draft, not authority. Accept synonyms, equivalent "
    "wording, defensible interpretations, and valid corrections to a flawed question. "
    "Use correct for a substantively correct answer; incorrect for a missed core concept. "
    "Speak directly to the learner as 'you', never 'the student'. Never discuss grading keys, "
    "the expected answer, or your assessment process. In explanation, address the answer directly "
    "and explain why it is correct or incorrect. In correction, teach the correct reasoning. "
    "In example, provide a concrete illustration. Always fill all three fields with meaningful "
    "text; only explanation will be shown for a correct answer. "
    "For hint requests, give a hint without revealing the answer; use hint. If you cannot reliably "
    "assess the answer, use uncertain and ask a clarifying question; never invent an error. "
    "Do not ask the next quiz question. Keep the review under 250 words."
)

CHOICE_QUALITY_PROMPT = (
    "You are checking a proposed multiple-choice study question before a learner sees it. Use the supplied "
    "source passages as the authority. Approve it only when the stem asks one clear, answerable thing; every "
    "option is a direct answer to that same thing; exactly one option is supported as correct; and the remaining "
    "options are plausible but clearly wrong. Reject options that merely repeat the premise, evade the question, "
    "or make a different claim than the stem asks about. Read the question word precisely: for a why, purpose, "
    "advantage, comparison, or difference question, the correct option must give that reason, advantage, or "
    "difference, rather than only restating a fact already embedded in the stem. Do not improve the answer yourself. "
    "Set valid=false whenever stem_answered or distractors_answer_stem is false, and give one short, actionable "
    "issue when regeneration is needed."
)


def requested_count(message):
    """Handle common counts exactly; the request model handles other phrasing."""
    words = {w: i for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
    text = re.sub(r"\bone (?:question )?at a time\b", "", message.lower())
    number = r"(\d+|" + "|".join(words) + r")"
    matches = re.findall(number + r"\s*(?:total\s+)?questions?\b|\bquestions?\s*(?:[:=]|of)?\s*" + number + r"\b|" + number + r"\s+total\b", text)
    if not matches:
        return None
    token = next(value for value in matches[-1] if value)
    count = int(token) if token.isdigit() else words[token]
    if not 1 <= count <= 50:
        raise ValueError("Choose between 1 and 50 questions per quiz.")
    return count


def windows(books, focus=""):
    result = []
    terms = set(re.findall(r"\w{4,}", focus.lower()))
    for item, chunks in books:
        primary = [c for c in chunks if c.get("variant") == "clean"] or chunks
        # Exclude clearly labelled publishing matter, not arbitrary first/last pages.
        useful = [c for c in primary if not re.search(
            r"copyright|table of contents|colophon|about the author|^index$", c.get("chapter", ""), re.I)]
        primary = useful or primary
        for start in range(0, len(primary), 2):
            group = primary[start:start + 3]
            text = " ".join(c.get("chapter", "") + " " + c["text"] for c in group).lower()
            result.append({"document_id": item["id"], "chunk_ids": [c["id"] for c in group],
                           "score": sum(term in text for term in terms)})
    if terms:
        relevant = [w for w in result if w["score"] > 0]
        if relevant:
            result = relevant
    return result


def select_windows(available, total):
    # Round-robin across documents; evenly spread each document's windows.
    groups = {}
    for window in available:
        groups.setdefault(window["document_id"], []).append(window)
    keys = list(groups)
    selected = []
    for index in range(total):
        key = keys[index % len(keys)]
        group = groups[key]
        turns = (total - 1 - keys.index(key)) // len(keys) + 1
        slot = index // len(keys)
        position = min(len(group) - 1, int((slot + .5) * len(group) / turns))
        selected.append(group[position])
    return selected


def coverage_windows(root, books, focus=""):
    """Build narrow, distinct study windows across the selected material."""
    source_windows = windows(books, focus)
    try:
        from app.rag.overview import concept_windows
        concepts = concept_windows(root, books, focus)
    except (OSError, ValueError, KeyError):
        concepts = []
    projected = []
    for concept_window in concepts:
        item, chunks = next((book for book in books if book[0]["id"] == concept_window["document_id"]), (None, []))
        if not item:
            continue
        hits = {chunk["id"] for chunk in candidates(chunks, concept_window.get("concept", ""), limit=3)}
        choices = [window for window in source_windows if window["document_id"] == item["id"]]
        if choices:
            closest = max(choices, key=lambda window: len(hits & set(window["chunk_ids"])))
            projected.append({**closest, "concept": concept_window.get("concept", "")})
    result, seen = [], set()
    for window in [*projected, *source_windows]:
        signature = (window["document_id"], tuple(window["chunk_ids"]))
        if signature not in seen:
            result.append(window)
            seen.add(signature)
    return result


def plan_windows(root, books, focus, total, seed=""):
    available = coverage_windows(root, books, focus)
    plan = select_windows(available, total) if available else []
    # Rotate a complete plan so fresh quizzes do not all open on passage one.
    if len(plan) > 1 and seed:
        offset = int(seed[:8], 16) % len(plan)
        plan = plan[offset:] + plan[:offset]
    return plan, len(available)


def plan_needs_refresh(quiz, available):
    plan = quiz.get("window_plan", [])
    expected = min(quiz.get("total", 0), len(available))
    signatures = {(window.get("document_id"), tuple(window.get("chunk_ids", []))) for window in plan}
    return (quiz.get("plan_version") != 2 or len(plan) < quiz.get("total", 0)
            or len(signatures) < expected)


async def bounded(llm, stage, prompt, data, sources):
    """Keep schema, student request, reply reserve, and margin inside the budget."""
    data = {**data, "sources": []}
    base = estimate(structured_messages(stage, prompt, data))
    if base > input_limit() - 128:
        raise ValueError("This quiz answer or request is too long for the context window. Please shorten it.")
    used = []
    # Compact metadata is enough for the model; full citation metadata stays on disk.
    for source in sources:
        entry = {k: source[k] for k in ("chunk_id", "text", "location")}
        proposed = {**data, "sources": data["sources"] + [entry]}
        if estimate(structured_messages(stage, prompt, proposed)) <= min(input_limit(), base + 1200):
            data = proposed
            used.append(source)
    if sources and not used:
        raise ValueError("Not enough context space for a quiz passage. Increase CONTEXT_WINDOW or shorten your answer.")
    result = await structured(llm, stage, prompt, data)
    return result, used


def completion(quiz):
    correct = sum(r["verdict"] == "correct" for r in quiz["results"])
    return f'Quiz complete: **{correct} of {quiz["total"]} correct**. Choose Review missed answers to revisit any mistakes, or start a new quiz.'


def missed_review(quiz):
    missed = [r for r in quiz.get("results", []) if r["verdict"] in {"incorrect", "partial"}]
    if not missed:
        return "No missed answers are saved for this quiz yet.", []
    sections, sources = [], []
    for record in missed:
        options = "\n\n".join(f'{chr(65+i)}. {option}' for i, option in enumerate(record.get("options", [])))
        sections.append(f'**Question {record.get("number", "")}: {record.get("question", record.get("topic", ""))}**\n\n'
                        + (options + "\n\n" if options else "") +
                        f'Your answer: {record.get("student_answer", "Not recorded in this older quiz.")}\n\n'
                        f'**Incorrect**\n\n{record.get("review", "Review this concept with Professor.")}')
        for source in record.get("sources", []):
            if not any((s["document_id"], s["chunk_id"]) == (source["document_id"], source["chunk_id"]) for s in sources):
                sources.append({**source, "label": f"S{len(sources) + 1}"})
    return "\n\n".join(sections), sources


def selected_option(message, quiz):
    options = quiz.get("options", [])
    if not options:
        return None
    match = re.fullmatch(r"\s*(?:(?:option|answer)\s*)?([a-d])[.)!]?\s*", message, re.I)
    if match:
        return ord(match[1].upper()) - 65
    return next((i for i, option in enumerate(options) if message.strip().casefold() == option.strip().casefold()), None)


def answer_index(quiz):
    options = quiz.get("options", [])
    key = quiz.get("answer_key", quiz.get("expected_answer", ""))
    matches = [i for i, option in enumerate(options) if option.strip().casefold() == key.strip().casefold()]
    if len(matches) == 1:
        return matches[0]
    if quiz.get("answer_key"):
        raise ValueError("The answer key does not match an option. Ask Professor to regenerate the question.")
    index = quiz.get("correct_index")
    if type(index) is not int or not 0 <= index < len(options):
        raise ValueError("This question has no valid answer key. Ask Professor to regenerate it.")
    return index


def choice_question_problem(data):
    """Return a repair note when a generated choice question cannot be graded safely."""
    options = data.get("options", [])
    normalized = [re.sub(r"\s+", " ", option).strip().casefold() for option in options]
    if len(normalized) != 4 or len(set(normalized)) != 4:
        return "The four options must be meaningfully distinct; the previous set repeated an option."
    answer = re.sub(r"\s+", " ", data.get("correct_answer", "")).strip().casefold()
    if sum(option == answer for option in normalized) != 1:
        return "The correct_answer must copy exactly one of the four options."
    # A response option must contribute an answer, not echo the information the
    # learner was just asked to reason about. This is a general MCQ contract;
    # the model critic below still handles the subtler semantic cases.
    stem_terms = set(re.findall(r"\w{3,}", data.get("question", "").casefold()))
    answer_terms = set(re.findall(r"\w{3,}", answer))
    if len(answer_terms) >= 4 and len(answer_terms - stem_terms) <= 1:
        return "The correct option mostly repeats the wording of the question instead of supplying its answer."
    return ""


async def choice_quality_problem(llm, data, sources):
    """Ask the tutor for a semantic check that deterministic schema checks cannot provide."""
    review, _ = await bounded(llm, "choice quality", CHOICE_QUALITY_PROMPT,
                              {"question": data["question"], "options": data["options"],
                               "correct_answer": data["correct_answer"],
                               "expected_answer": data["expected_answer"]}, sources)
    if review["valid"] and review["stem_answered"] and review["distractors_answer_stem"]:
        return ""
    return review["issue"] or "The choices do not clearly answer the question. Regenerate the entire question."


def repeated_question_problem(question, previous_questions):
    """Catch near-identical quiz prompts before they become another turn."""
    candidate = re.sub(r"\W+", " ", question).casefold().strip()
    # Question stems such as "What is the primary purpose of" are intentionally
    # reusable. Compare the topic-bearing words instead, or a small model will
    # reject a valid comments question just because the previous question was
    # phrased similarly about scripts.
    framing = {"what", "which", "where", "when", "why", "how", "the", "and", "for", "with", "from",
               "that", "this", "these", "does", "purpose", "primary", "main", "best", "following",
               "describe", "defines", "used", "using", "about", "into", "your", "r"}
    candidate_words = {word for word in re.findall(r"\w{3,}", candidate) if word not in framing}
    for previous in previous_questions:
        earlier = re.sub(r"\W+", " ", previous).casefold().strip()
        earlier_words = {word for word in re.findall(r"\w{3,}", earlier) if word not in framing}
        shared = len(candidate_words & earlier_words) / max(1, min(len(candidate_words), len(earlier_words)))
        wording = SequenceMatcher(None, candidate, earlier).ratio()
        if shared >= .75 or (wording >= .86 and shared >= .5):
            return "This question substantially repeats an earlier quiz question. Test a different main idea instead."
    return ""


def choice_feedback_problem(data):
    feedback = " ".join(data.get(field, "") for field in ("explanation", "correction", "example"))
    if "?" in feedback:
        return "This is answer feedback, not the next quiz turn. Do not ask any question."
    return ""


async def quiz_turn(root, identifiers, message, quiz, llm, recent=None):
    quiz = deepcopy(quiz)  # A failed model call must not advance saved progress.
    # Repair the old router's trailing format request scored as an answer.
    results = quiz.get("results", [])
    if results and re.search(r"^\s*(?:please\s+)?(?:make|change|switch|convert)\b.*\bmultiple[ -]choice\b", results[-1].get("student_answer", ""), re.I):
        results.pop()
        quiz.update(cursor=len(results), phase="question", active=True)
    acknowledgement = ""
    if REVIEW.search(message):
        text, sources = missed_review(quiz)
        return text, quiz, sources
    choice_answer = selected_option(message, quiz)
    if quiz.get("version") == 2 and choice_answer is None and not NEXT.fullmatch(message) and (quiz.get("active") or CHANGE.search(message)):
        intent, _ = await bounded(llm, "quiz intent",
            "Understand the student's latest message BEFORE grading. Requests to change format, difficulty, "
            "wording, topic, or regenerate are change, never answer. Asking a question or requesting an "
            "explanation is discuss. A substantive attempt at the pending question is answer. "
            "Return the desired format, concise updated guidelines, and a brief friendly acknowledgement "
            "for changes only. Preserve existing preferences unless changed. Do not grade or reveal answers.",
            {"message": message, "pending_question": quiz.get("pending_question", ""),
             "format": quiz.get("format", "short_answer"), "guidelines": quiz.get("guidelines", ""),
             "recent": [{"role": m["role"], "content": m["content"][:300]} for m in (recent or [])[-2:]]}, [])
        action = "change" if CHANGE.search(message) else intent["action"]
        if action == "discuss":
            return None, quiz, []
        if action == "change":
            quiz["format"] = "multiple_choice" if re.search(r"multiple[ -]choice", message, re.I) else intent["format"]
            quiz["guidelines"] = intent["guidelines"] or message[:300]
            if intent["focus"] is not None:
                quiz["focus"] = intent["focus"]
            acknowledgement = intent["acknowledgement"]
            if quiz.get("phase") == "complete":
                quiz.update(cursor=0, results=[], window_reviews=[])
            elif quiz.get("phase") == "review":
                quiz["cursor"] += 1
            quiz.update(active=True, phase="question", pending_question="")
            quiz["regenerate_request"] = message[:500]
            count = requested_count(message) or intent["count"]
            if count is not None:
                if count <= len(quiz["results"]):
                    quiz.update(cursor=0, results=[], window_reviews=[])
                quiz["total"] = count
                if identifiers:
                    quiz["window_plan"], quiz["available_windows"] = plan_windows(
                        root, library(root, identifiers), quiz.get("focus", ""), count, uuid4().hex)
                    quiz["plan_version"] = 2
                else:
                    quiz["window_plan"] = []
            elif intent["focus"] is not None and identifiers:
                quiz["window_plan"], quiz["available_windows"] = plan_windows(
                    root, library(root, identifiers), quiz["focus"], quiz["total"], uuid4().hex)
                quiz["plan_version"] = 2
        elif action == "hint":
            quiz["hint_requested"] = True
    if quiz.get("phase") == "complete":
        return (completion(quiz) if NEXT.fullmatch(message) else None), quiz, []
    books = library(root, identifiers)
    if quiz.get("version") != 2 or quiz.get("document_ids") != identifiers:
        count = requested_count(message)
        intent, _ = await bounded(llm, "quiz request",
            "Interpret the student's quiz request. Default to 10 questions unless they specify a total. "
            "Default to multiple_choice unless the learner requests another format. "
            "'One question at a time' describes pacing, NOT total count. Return a short subject focus "
            "only if explicitly requested; use an empty focus for the whole material or main ideas. "
            "Never infer a total from page numbers or a course title. For a general quiz without materials, "
            "resolve 'this concept' from recent conversation.",
            {"request": message, "has_materials": bool(identifiers),
             "recent": [{"role": m["role"], "content": m["content"][:400]} for m in (recent or [])[-2:]]}, [])
        total = count if count is not None else intent["count"]
        available = coverage_windows(root, books, intent["focus"])
        if identifiers and not available:
            raise ValueError("No readable passages are available for this quiz.")
        seed = uuid4().hex
        window_plan = select_windows(available, total) if available else []
        if len(window_plan) > 1:
            offset = int(seed[:8], 16) % len(window_plan)
            window_plan = window_plan[offset:] + window_plan[:offset]
        quiz = {"version": 2, "active": True, "document_ids": identifiers, "total": total,
                "cursor": 0, "results": [], "phase": "question", "pending_question": "",
                "focus": intent["focus"], "format": "multiple_choice" if re.search(r"multiple[ -]choice", message, re.I) else intent["format"], "guidelines": intent["guidelines"] or message[:300],
                "window_plan": window_plan, "window_reviews": [], "available_windows": len(available),
                "plan_version": 2, "turns": 0}
    if identifiers:
        available = coverage_windows(root, books, quiz.get("focus", ""))
        if plan_needs_refresh(quiz, available):
            quiz["window_plan"], quiz["available_windows"] = plan_windows(
                root, books, quiz.get("focus", ""), quiz["total"], uuid4().hex)
            quiz["plan_version"] = 2
    if quiz.get("phase") == "review":
        if NEXT.fullmatch(message):
            quiz.update(cursor=quiz["cursor"] + 1, phase="question", pending_question="")
        else:
            return None, quiz, []
    cursor = quiz["cursor"]
    if not quiz.get("pending_question"):
        sources, item = [], {"id": ""}
        if books:
            window = quiz["window_plan"][cursor]
            item, chunks = next(b for b in books if b[0]["id"] == window["document_id"])
            chosen = [c for c in chunks if c["id"] in window["chunk_ids"]]
            if window.get("concept"):
                from app.rag.library import candidates
                chosen = candidates(chosen, window["concept"], limit=3) or chosen[:3]
            sources = passages(item, chosen)
        choice = quiz.get("format") == "multiple_choice"
        prompt = WINDOW_PROMPT + (" Provide four distinct plausible options without letter prefixes and exactly one defensible correct option. Copy its exact option text verbatim into correct_answer. Never supply an option number. Do not include synonymous options or reveal the answer in the question. Before returning, compare every option with the other three so that no two choices state the same answer." if choice else "")
        previous_questions = [r["question"] for r in quiz["results"]]
        request = {"focus": quiz["focus"], "format": quiz.get("format", "short_answer"),
                   "guidelines": quiz.get("guidelines", ""), "latest_request": quiz.pop("regenerate_request", ""),
                   "concept": window.get("concept", "") if books else "",
                   "previous_questions": [question[:180] for question in previous_questions]}
        repair = ""
        for attempt in range(3):
            attempt_prompt = prompt if not repair else (
                prompt + "\n\nYour previous draft could not be used: " + repair
                + " Regenerate the whole question with four new, distinct choices."
            )
            data, sources = await bounded(llm, "quiz choices" if choice else "quiz window", attempt_prompt,
                                           request, sources)
            repair = choice_question_problem(data) if choice else ""
            if not repair:
                repair = repeated_question_problem(data["question"], previous_questions)
            if not repair and choice:
                repair = await choice_quality_problem(llm, data, sources)
            if not repair:
                break
        if repair:
            raise ValueError("Professor could not form a valid multiple-choice question after retrying. Please try another topic.")
        # Reference links come from the exact bounded input, never model-authored IDs.
        quiz.update(pending_question=data["question"], expected_answer=data["expected_answer"], sources=sources,
                    question_id=uuid4().hex)
        quiz["options"] = data.get("options", [])
        quiz["answer_key"] = data.get("correct_answer", "")
        quiz["correct_index"] = answer_index(quiz) if choice else None
        quiz["window_reviews"] = [r for r in quiz["window_reviews"] if r["number"] != cursor + 1]
        quiz["window_reviews"].append({"number": cursor + 1, "summary": data["summary"],
                                       "document_id": item["id"], "chunk_ids": [s["chunk_id"] for s in sources], "question": data["question"]})
        options = "\n\n" + "\n\n".join(f'**{chr(65+i)}.** {option}' for i, option in enumerate(quiz["options"])) if choice else ""
        intro = acknowledgement + "\n\n" if acknowledgement else ""
        return f'{intro}**Question {cursor + 1} of {quiz["total"]}**\n\n{data["question"]}{options}', quiz, sources
    if NEXT.fullmatch(message):
        return "Answer the current question first, or ask for a hint.\n\n" + quiz["pending_question"], quiz, quiz["sources"]
    hint = quiz.pop("hint_requested", False) or bool(re.search(r"\bhint\b", message, re.I))
    if choice_answer is not None and not hint:
        options = quiz["options"]
        correct_index = answer_index(quiz)
        quiz["correct_index"] = correct_index
        verdict = "correct" if choice_answer == correct_index else "incorrect"
        feedback_prompt = (
            "You are Professor explaining a multiple-choice answer. The application has already matched "
            "the student's selection against the saved answer key. The supplied result is final; do not "
            "re-grade the selection or claim a displayed option is invalid. Explain the underlying concept "
            "naturally, addressing the learner as you. For correct answers, explain why the selected text "
            "answers the question. For incorrect answers, explain the distinction from the correct text, "
            "then teach the concept and give a concrete example. Avoid referring to internal option numbers. "
            "Fill explanation, correction, and example; only explanation is displayed when correct."
            " This response appears beneath the answered choices. Do not ask a new question, offer new "
            "choices, or move the quiz forward; the learner uses Next question when ready."
        )
        feedback_request = {"question": quiz["pending_question"], "result": verdict,
                            "selected_answer": {"letter": chr(65 + choice_answer), "text": options[choice_answer]},
                            "correct_answer": {"letter": chr(65 + correct_index), "text": options[correct_index]}}
        repair = ""
        for attempt in range(2):
            attempt_prompt = feedback_prompt if not repair else feedback_prompt + "\n\nYour previous draft broke the feedback contract: " + repair + " Rewrite it as an explanation only."
            data, _ = await bounded(llm, "choice feedback", attempt_prompt, feedback_request, quiz["sources"])
            repair = choice_feedback_problem(data)
            if not repair:
                break
        if repair:
            raise ValueError("Professor could not finish this answer review without starting a new question. Please try the answer again.")
    else:
        data, _ = await bounded(llm, "quiz assessment", GRADE_PROMPT,
        {"question": quiz["pending_question"], "expected_answer": quiz["expected_answer"],
         "student_answer": message, "hint_requested": hint, "options": quiz.get("options", []),
         "correct_option": quiz.get("correct_index"), "selected_option": choice_answer,
         "selection_is_correct": choice_answer == quiz.get("correct_index") if choice_answer is not None else None}, quiz["sources"])
        verdict = "hint" if hint else data["verdict"]
    if verdict == "incorrect" and not all(data[k].strip() for k in ("correction", "example")):
        raise ValueError("Professor could not complete the concept review. Please retry your answer.")
    heading = {"correct": "Correct", "incorrect": "Incorrect", "hint": "Hint", "uncertain": "Please clarify"}[verdict]
    review = "\n\n".join(data[k].strip() for k in ("explanation", "correction", "example") if data[k].strip()) if verdict == "incorrect" else data["explanation"]
    response = f'**{heading}**\n\n{review}'
    quiz["turns"] += 1
    if verdict in {"correct", "incorrect"}:
        quiz["results"].append({"number": cursor + 1, "question": quiz["pending_question"],
                                "question_id": quiz.get("question_id", ""),
                                "student_answer": message, "verdict": verdict, "review": review,
                                "options": quiz.get("options", []),
                                "selected_index": choice_answer, "correct_index": quiz.get("correct_index"),
                                "sources": quiz["sources"]})
        finished = len(quiz["results"]) == quiz["total"]
        quiz.update(phase="complete" if finished else "review", active=not finished)
        response += "\n\n" + (completion(quiz) if finished else "Ask about anything unclear, or choose Next question when ready.")
    return response, quiz, quiz["sources"]


def public_question(quiz):
    """Never expose a pending answer key through chat or conversation APIs."""
    if not quiz.get("options") or not quiz.get("question_id"):
        return {}
    result = next((r for r in reversed(quiz.get("results", []))
                   if r.get("question_id") == quiz["question_id"]), None)
    return {"id": quiz["question_id"], "question": quiz["pending_question"],
            "options": quiz["options"], "number": quiz["cursor"] + 1, "total": quiz["total"],
            "answered": bool(result),
            **({k: result.get(k) for k in ("selected_index", "correct_index", "verdict")} if result else {})}
