import asyncio

import httpx

from app import main
from app.agents import activity
from app.storage.conversation_store import ConversationStore


def test_cancel_request_preserves_session_and_allows_retry(tmp_path, monkeypatch):
    store = ConversationStore(tmp_path)
    identifier = store.create_id()
    store.save(identifier, [], quiz={"active": True, "question_id": "saved"})
    before = store._path(identifier).read_bytes()
    monkeypatch.setattr(main, "store", store)

    async def scenario():
        started = asyncio.Event()

        class Agent:
            async def reply(self, *args, **kwargs):
                started.set()
                await asyncio.sleep(60)

        monkeypatch.setattr(main, "agent", Agent())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://test") as client:
            pending = asyncio.create_task(client.post("/api/chat", json={
                "message": "explain", "conversation_id": identifier, "request_id": "new",
            }))
            await asyncio.wait_for(started.wait(), 2)
            stale = await client.post(f"/api/conversations/{identifier}/cancel?request_id=old")
            assert stale.json() == {"cancelled": False}
            assert not pending.done()
            cancelled = await client.post(f"/api/conversations/{identifier}/cancel?request_id=new")
            assert cancelled.json() == {"cancelled": True}
            response = await asyncio.wait_for(pending, 2)
            assert response.status_code == 409
            assert "cancelled" in response.json()["detail"]
            assert identifier not in activity.active
            assert identifier not in activity.tasks
            assert store._path(identifier).read_bytes() == before

            class SuccessAgent:
                async def reply(self, *args, **kwargs):
                    store.save(identifier, [{"role": "assistant", "content": "Ready"}])
                    return identifier, "Ready"

            monkeypatch.setattr(main, "agent", SuccessAgent())
            retry = await client.post("/api/chat", json={
                "message": "explain", "conversation_id": identifier, "request_id": "retry",
            })
            assert retry.status_code == 200
            assert retry.json()["message"] == "Ready"

    asyncio.run(scenario())
