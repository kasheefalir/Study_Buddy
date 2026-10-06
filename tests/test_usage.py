import asyncio

from app.llm.usage import record_usage, summarize, track_usage, usage_stage


def test_counts_all_stages_and_restores_context():
    with track_usage() as calls:
        record_usage({"prompt_eval_count": 12, "eval_count": 4}, "test")
        with usage_stage("verification"):
            record_usage({"prompt_eval_count": 20, "eval_count": 2}, "test")
    assert summarize(calls) == {
        "input_tokens": 32, "output_tokens": 6,
        "calls": [
            {"stage": "answer", "model": "test", "input_tokens": 12, "output_tokens": 4},
            {"stage": "verification", "model": "test", "input_tokens": 20, "output_tokens": 2},
        ],
    }
    record_usage({"prompt_eval_count": 99}, "outside")
    assert len(calls) == 2


def test_missing_counts_are_not_zero():
    with track_usage() as calls:
        record_usage({"prompt_eval_count": True, "eval_count": -1}, "test")
    assert summarize(calls)["input_tokens"] is None
    assert summarize(calls)["output_tokens"] is None
    assert summarize([])["input_tokens"] is None


def test_concurrent_requests_are_isolated():
    async def worker(value):
        with track_usage() as calls:
            with usage_stage(str(value)):
                await asyncio.sleep(0)
                record_usage({"prompt_eval_count": value, "eval_count": 1}, "test")
            return summarize(calls)

    async def run():
        return await asyncio.gather(worker(5), worker(10))
    first, second = asyncio.run(run())
    assert first["input_tokens"] == 5
    assert second["input_tokens"] == 10
    assert first["calls"][0]["stage"] == "5"
    assert second["calls"][0]["stage"] == "10"


def test_agent_persists_usage_and_does_not_send_it_as_context(tmp_path):
    from app.agents.chat_agent import ChatAgent
    from app.storage.conversation_store import ConversationStore

    class MeteredLLM:
        async def chat(self, messages):
            assert all(set(m) == {"role", "content"} for m in messages)
            record_usage({"prompt_eval_count": 100, "eval_count": 20}, "test")
            return "An answer"

    store = ConversationStore(tmp_path)
    agent = ChatAgent(MeteredLLM(), store)
    identifier, _ = asyncio.run(agent.reply("First question"))
    asyncio.run(agent.reply("Follow up", identifier))
    replies = [m for m in store.load(identifier) if m["role"] == "assistant"]
    assert len(replies) == 2
    assert all(m["usage"]["input_tokens"] == 100 for m in replies)
