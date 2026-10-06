import asyncio

from app.agents.chat_agent import ChatAgent
from app.storage.conversation_store import ConversationStore


class FakeLLM:
    def __init__(self):
        self.requests = []

    async def chat(self, messages):
        self.requests.append(messages)
        return "A useful answer"


def test_agent_preserves_follow_up_context(tmp_path):
    llm = FakeLLM()
    agent = ChatAgent(llm, ConversationStore(tmp_path))

    conversation_id, _ = asyncio.run(agent.reply("What is regularization?"))
    asyncio.run(agent.reply("Explain that more simply.", conversation_id))

    second_request = llm.requests[1]
    assert [message["content"] for message in second_request[-3:]] == [
        "What is regularization?",
        "A useful answer",
        "Explain that more simply.",
    ]


def test_model_context_is_bounded_while_archive_is_preserved(tmp_path):
    llm = FakeLLM()
    store = ConversationStore(tmp_path, max_messages=2)
    identifier = store.create_id()
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(8)]
    store.save(identifier, history, memory="Focus on biology")
    asyncio.run(ChatAgent(llm, store).reply("Next question", identifier))
    sent = llm.requests[0]
    assert len(sent) == 5  # System, saved notes, two recent messages, new question.
    assert "Focus on biology" in sent[1]["content"]
    assert [m["content"] for m in sent[2:]] == ["6", "7", "Next question"]
    assert len(store.load(identifier)) == 10
    assert "earlier_student_messages" in sent[1]["content"]


def test_quiz_remembers_pending_question_after_reload(tmp_path):
    class QuizLLM(FakeLLM):
        async def chat(self, messages):
            self.requests.append(messages)
            return "What kind of outcome does logistic regression predict?"

    model = QuizLLM()
    store = ConversationStore(tmp_path)
    identifier, _ = asyncio.run(ChatAgent(model, store).reply(
        "Quiz me on logistic regression, one question at a time.", document_id="a" * 32))
    assert len(model.requests) == 1  # No retrieval or answer rewrite for concept practice.
    assert store.quiz(identifier)["pending_question"].endswith("predict?")
    reloaded = ConversationStore(tmp_path)
    asyncio.run(ChatAgent(model, reloaded).reply("A binary outcome", identifier, document_id="a" * 32))
    prompt = model.requests[-1]
    assert "pending_question" in prompt[1]["content"]
    assert prompt[-2]["content"].endswith("predict?")
    assert prompt[-1]["content"] == "A binary outcome"
    assert reloaded.quiz(identifier)["turns"] == 2
    reloaded.save(identifier, reloaded.load(identifier), memory="Use simple examples")
    assert reloaded.quiz(identifier)["active"]
    asyncio.run(ChatAgent(model, reloaded).reply("Stop the quiz", identifier))
    assert reloaded.quiz(identifier) == {}
