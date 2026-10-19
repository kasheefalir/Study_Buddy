"""Experimental batched check; not selected by the live writer."""
from app.agents.grounded_answer import evidence_check_request, check_schema_for, parse_checks, render_answer
from app.llm.usage import usage_stage


async def verify_batch(llm, answer, sources):
    render_answer(answer.model_dump_json(), sources)
    schema = check_schema_for(len(answer.points))
    request = evidence_check_request(answer, sources)
    with usage_stage("deepseek batched support check"):
        raw = await llm.structured_plan(request, schema)
    return parse_checks(raw, len(answer.points))
