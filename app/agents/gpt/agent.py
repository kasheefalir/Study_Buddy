from pathlib import Path

from app.agents.chat_agent import ChatAgent
from app.agents.quiz import quiz_turn

ROOT = Path(__file__).parent


class GPTAgent(ChatAgent):
    """Model-owned intent with on-demand questions and shared transactional state."""

    router_prompt = (ROOT / "router.md").read_text(encoding="utf-8")
    retrieval_prompt = (ROOT / "retrieval.md").read_text(encoding="utf-8")
    system_prompt = (ROOT / "professor.md").read_text(encoding="utf-8")

    async def quiz_step(self, *args, **kwargs):
        return await quiz_turn(*args, **kwargs, prepare_all=False)
