import asyncio
import pytest

from app.agents.tasks import task_for, task_prompt, PROMPTS
from app.agents.chat_agent import ChatAgent
from app.storage.conversation_store import ConversationStore


@pytest.mark.parametrize("message,expected", [
    ("Quiz me on regression", "quiz"),
    ("Explain more simply", "simplify"),
    ("Summarize the PowerPoint", "summary_material"),
    ("Summarize the R introduction in my saved link", "chat"),
    ("Give me a summary of that online tutorial", "chat"),
    ("Summarize our conversation about the slides", "summary_conversation"),
    ("Stop the quiz", "chat"),
    ("I think it is binary", "quiz"),
])
def test_typed_task_routing(message, expected):
    assert task_for(message, "auto", {"active": True}) == expected


def test_explicit_modes_and_prompt_files():
    assert task_for("Something", "simplify", {}) == "simplify"
    assert "Professor" in (PROMPTS / "professor.md").read_text()
    assert "ONE" in task_prompt("quiz")
    with pytest.raises(ValueError):
        task_for("Hello", "../bad", {})


def test_recap_and_hint_preserve_quiz_and_skip_retrieval(tmp_path):
    class Model:
        def __init__(self):
            self.calls = []

        async def chat(self, messages):
            self.calls.append(messages)
            return "Think about what a probability represents. Does that help?"

    store = ConversationStore(tmp_path)
    identifier = store.create_id()
    state = {"active": True, "topic": "regression", "pending_question": "What does it predict?", "turns": 1}
    store.save(identifier, [{"role": "assistant", "content": "What does it predict?"}], quiz=state)
    model = Model()
    agent = ChatAgent(model, store)
    asyncio.run(agent.reply("Recap our discussion of the slides", identifier, "a" * 32, task="summary_conversation"))
    assert len(model.calls) == 1
    assert "Recap Conversation" in model.calls[0][0]["content"]
    assert store.quiz(identifier) == state
    asyncio.run(agent.reply("A hint please", identifier))
    assert store.quiz(identifier)["pending_question"] == state["pending_question"]
