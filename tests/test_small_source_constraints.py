import asyncio
import json

import pytest

from app.agents.study_tools import OUTPUTS, structured
from app.agents.small_models.source_constraints import material_schema


@pytest.mark.parametrize("stage,data,expected", [
    ("retrieval plan", {"selected_materials": [{"id": "a"}, {"id": "b"}]}, ["a", "b"]),
    ("material tool selection", {"session_materials": [{"id": "a"}]}, ["a"]),
    ("retrieval sufficiency", {"coverage": [{"document_id": "b"}], "evidence": []}, ["b"]),
])
def test_scoped_enum_without_mutating_base(stage, data, expected):
    original = OUTPUTS[stage].model_json_schema()
    schema, allowed = material_schema(original, stage, data)
    assert schema["properties"]["document_ids"]["items"]["enum"] == expected
    assert list(allowed) == expected
    assert "enum" not in original["properties"]["document_ids"]["items"]


def test_empty_scope_requires_empty_selection():
    schema, allowed = material_schema(OUTPUTS["retrieval plan"].model_json_schema(), "retrieval plan", {})
    assert schema["properties"]["document_ids"]["maxItems"] == 0
    assert allowed == ()


@pytest.mark.parametrize("name,constrained", [
    ("llama3.2:3b", True), ("phi4-mini:latest", True),
    ("gpt-oss:20b", False), ("deepseek-r1:8b", False),
])
def test_live_structured_call_and_model_isolation(name, constrained):
    class Client:
        model = name
        ids = ["available"]

        async def structured_plan(self, messages, schema):
            field = schema["properties"]["document_ids"]["items"]
            assert ("enum" in field) == constrained
            if constrained:
                assert field["enum"] == ["available"]
                assert '"enum": ["available"]' in messages[0]["content"]
            return json.dumps({"reasoning": "Use selected material", "query": "definition", "document_ids": self.ids})

    client = Client()
    data = {"selected_materials": [{"id": "available"}]}
    result = asyncio.run(structured(client, "retrieval plan", "Plan", data))
    assert result["document_ids"] == ["available"]
    client.ids = ["invented"]
    if constrained:
        with pytest.raises(ValueError):
            asyncio.run(structured(client, "retrieval plan", "Plan", data))
    else:
        assert asyncio.run(structured(client, "retrieval plan", "Plan", data))["document_ids"] == ["invented"]
