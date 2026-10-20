"""Lossless envelope handling; never repairs facts, fields, or validation errors."""
import json
import re


def strip_json_fence(raw):
    text = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n(.*)\n```", text, flags=re.DOTALL)
    return fence.group(1) if fence else text


def validated_output(raw, model):
    try:
        return model.model_validate_json(raw)
    except ValueError as original:
        text = strip_json_fence(raw)
        try:
            value = json.loads(text)
            schema = model.model_json_schema()
            # Some providers wrap values in the schema's `properties` container.
            # Only discard exact schema metadata, never arbitrary response fields.
            if (isinstance(value, dict) and "properties" not in schema.get("properties", {})
                    and isinstance(value.get("properties"), dict)
                    and set(value) <= {"properties", "required", "title", "type"}
                    and all(value[key] == schema.get(key) for key in value if key != "properties")):
                value = value["properties"]
        except (ValueError, TypeError):
            raise original
        # After a recognized envelope is removed, report the actual field error
        # so bounded retries can fix it instead of seeing a misleading JSON error.
        return model.model_validate_json(json.dumps(value))
