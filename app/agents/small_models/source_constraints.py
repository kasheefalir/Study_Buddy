"""Production-safe ID constraints; no experimental planner/writer prompts."""
from copy import deepcopy

MODELS = frozenset({"llama3.2:3b", "phi4-mini", "phi4-mini:latest"})


def material_schema(schema, stage, data):
    """Constrain opaque IDs without changing stored IDs or introducing aliases."""
    if stage == "retrieval plan":
        identifiers = [item["id"] for item in data.get("selected_materials", [])]
    elif stage == "material tool selection":
        identifiers = [item["id"] for item in data.get("session_materials", [])]
    elif stage == "retrieval sufficiency":
        identifiers = [item["document_id"] for item in data.get("coverage", [])]
    else:
        return schema, None
    allowed = tuple(dict.fromkeys(identifiers))
    constrained = deepcopy(schema)
    field = constrained["properties"]["document_ids"]
    if allowed:
        field["items"] = {"type": "string", "enum": list(allowed)}
    else:
        field["maxItems"] = 0
    return constrained, allowed


def validate_material_ids(result, allowed):
    if allowed is not None and not set(result["document_ids"]) <= set(allowed):
        raise ValueError("Professor selected a material outside the current retrieval scope.")
