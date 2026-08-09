"""Shared standard-library JSON schema validation helpers."""

from __future__ import annotations

import re
from typing import Any


def type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_value_against_schema(value: Any, schema: dict[str, Any], schemas: dict[str, Any], path: str) -> list[str]:
    if "$ref" in schema:
        ref = schema["$ref"]
        ref_schema = schemas.get(ref)
        if ref_schema is None:
            return [f"schema {path}: unresolved ref {ref}"]
        return validate_value_against_schema(value, ref_schema, schemas, path)

    errors: list[str] = []

    if "const" in schema and value != schema["const"]:
        errors.append(f"schema {path}: expected const {schema['const']!r}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"schema {path}: value {value!r} not in enum {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(type_matches(value, item) for item in expected_types):
            errors.append(f"schema {path}: expected type {expected_types!r}, got {type(value).__name__}")
            return errors

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"schema {path}: missing required field {key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            allowed = set(properties)
            for key in value:
                if key not in allowed:
                    errors.append(f"schema {path}: unexpected field {key}")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(validate_value_against_schema(value[key], child_schema, schemas, f"{path}.{key}"))

    if isinstance(value, list) and "items" in schema:
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"schema {path}: array has {len(value)} items, below minItems {schema['minItems']!r}")
        for index, item in enumerate(value):
            errors.extend(validate_value_against_schema(item, schema["items"], schemas, f"{path}[{index}]"))

    if isinstance(value, str) and "pattern" in schema:
        if not re.search(schema["pattern"], value):
            errors.append(f"schema {path}: string does not match pattern {schema['pattern']!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"schema {path}: value {value!r} below minimum {schema['minimum']!r}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"schema {path}: value {value!r} above maximum {schema['maximum']!r}")

    return errors
