from __future__ import annotations

import re
from typing import Any


SIMULATION = "simulation"
UNDERSTANDING = "understanding"
FACT_OR_MEMORY = {"fact", "memory"}
LAYERS = FACT_OR_MEMORY | {UNDERSTANDING, SIMULATION}
STATUSES = {"verified", "user_confirmed", "user_stated", "inferred", "conflict", "unknown"}


def next_revision(existing: dict[str, Any]) -> int:
    revision = existing.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ValueError("revision must be a positive integer")
    return revision + 1


def validate_semantic_record_shape(record: dict[str, Any]) -> list[str]:
    allowed = {
        "id", "semantic_layer", "text", "source_refs", "status", "confidence",
        "sensitivity", "visibility", "created_at", "revision", "base_record_ids",
        "simulation_origin_id",
    }
    required = allowed - {"base_record_ids", "simulation_origin_id"}
    errors: list[str] = []
    missing = required - set(record)
    if missing:
        errors.append("missing fields: " + ", ".join(sorted(missing)))
    unexpected = set(record) - allowed
    if unexpected:
        errors.append("unexpected fields: " + ", ".join(sorted(unexpected)))
    record_id = record.get("id")
    if not isinstance(record_id, str) or not re.fullmatch(r"rec_[a-z0-9_]+", record_id):
        errors.append("id must match rec_[a-z0-9_]+")
    if record.get("semantic_layer") not in LAYERS:
        errors.append("semantic_layer is invalid")
    if not isinstance(record.get("text"), str) or not record["text"].strip():
        errors.append("text must be non-empty")
    source_refs = record.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs or not all(
        isinstance(item, str) and re.fullmatch(r"src_[a-z0-9_]+", item) for item in source_refs
    ):
        errors.append("source_refs must contain src_[a-z0-9_]+ ids")
    if record.get("status") not in STATUSES:
        errors.append("status is invalid")
    confidence = record.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        errors.append("confidence must be between 0 and 1")
    if record.get("sensitivity") not in {"low", "medium", "high"}:
        errors.append("sensitivity is invalid")
    if record.get("visibility") not in {"private", "shareable", "blocked"}:
        errors.append("visibility is invalid")
    created_at = record.get("created_at")
    if not isinstance(created_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created_at):
        errors.append("created_at must be UTC ISO-8601 seconds")
    revision = record.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("revision must be a positive integer")
    return errors


def validate_semantic_record_graph(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        errors.extend(validate_semantic_record_shape(record))
        record_id = record.get("id")
        if not isinstance(record_id, str):
            errors.append("record id must be a string")
            continue
        if record_id in by_id:
            errors.append(f"duplicate record id: {record_id}")
        by_id[record_id] = record

    for record_id, record in by_id.items():
        layer = record.get("semantic_layer")
        origin_id = record.get("simulation_origin_id")
        base_ids = record.get("base_record_ids", [])

        if layer in FACT_OR_MEMORY and origin_id is not None:
            errors.append(f"{record_id}: {layer} cannot reference simulation_origin_id")
        if layer == SIMULATION:
            if not isinstance(base_ids, list) or not base_ids:
                errors.append(f"{record_id}: simulation requires base_record_ids")
            for base_id in base_ids if isinstance(base_ids, list) else []:
                if base_id not in by_id:
                    errors.append(f"{record_id}: unknown base record {base_id}")
                elif by_id[base_id].get("semantic_layer") == SIMULATION:
                    errors.append(f"{record_id}: simulation cannot use simulation as its base record")
        elif base_ids:
            errors.append(f"{record_id}: only simulation may define base_record_ids")

        if origin_id is not None:
            origin = by_id.get(origin_id)
            if origin is None:
                errors.append(f"{record_id}: unknown simulation origin {origin_id}")
            elif origin.get("semantic_layer") != SIMULATION:
                errors.append(f"{record_id}: simulation_origin_id must reference a simulation")
            elif layer != UNDERSTANDING:
                errors.append(f"{record_id}: only understanding may reference simulation_origin_id")
            elif record.get("status") != "user_confirmed":
                errors.append(f"{record_id}: understanding from simulation must be user_confirmed")
    return errors
