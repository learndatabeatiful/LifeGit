from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

try:
    from scripts.agent_jobs import create_job, get_job, load_capabilities
    from scripts.entry_definitions import entry_ids, get_entry
    from scripts.guided_session import (
        answer_question,
        complete_session,
        list_sessions,
        load_session,
        next_question,
        pause_session,
        resume_session,
        skip_question,
        start_session,
    )
    from scripts.local_security import (
        load_json_preserving_corrupt,
        require_identifier,
        resolve_within,
    )
    from scripts.privacy_review import confirm_privacy_review, create_privacy_review
    from scripts.share_projection import (
        build_local_projection,
        load_projection,
        save_card_png,
        update_card_copy,
    )
except ModuleNotFoundError:
    from agent_jobs import create_job, get_job, load_capabilities
    from entry_definitions import entry_ids, get_entry
    from guided_session import (
        answer_question,
        complete_session,
        list_sessions,
        load_session,
        next_question,
        pause_session,
        resume_session,
        skip_question,
        start_session,
    )
    from local_security import load_json_preserving_corrupt, require_identifier, resolve_within
    from privacy_review import confirm_privacy_review, create_privacy_review
    from share_projection import (
        build_local_projection,
        load_projection,
        save_card_png,
        update_card_copy,
    )


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: bytes
    content_type: str = "application/json"
    headers: dict[str, str] = field(default_factory=dict)


def _json(status: int, value: object) -> ApiResponse:
    return ApiResponse(
        status,
        (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8"),
    )


def _parse_json(body: bytes) -> dict:
    value = json.loads(body or b"{}")
    if not isinstance(value, dict):
        raise ValueError("JSON body must be an object")
    return value


class WebApi:
    def __init__(self, root: Path, clock: Callable[[], str]):
        self.root = root
        self.clock = clock

    def _session_snapshot(self, session_id: str) -> dict:
        session = load_session(self.root, session_id)
        question = next_question(self.root, session_id)
        projection_path = self.root / "outputs" / "cards" / f"{session_id}.card.json"
        return {
            "session": session,
            "next_question": question,
            "projection": (
                load_projection(self.root, session_id) if projection_path.exists() else None
            ),
        }

    def dispatch(
        self,
        method: str,
        path: str,
        body: bytes = b"",
        content_type: str = "application/json",
    ) -> ApiResponse:
        try:
            return self._dispatch(method, path, body, content_type)
        except FileNotFoundError as error:
            return _json(404, {"error": "not_found", "message": str(error)})
        except FileExistsError as error:
            return _json(409, {"error": "conflict", "message": str(error)})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return _json(400, {"error": "invalid_request", "message": str(error)})

    def _dispatch(
        self,
        method: str,
        path: str,
        body: bytes,
        content_type: str,
    ) -> ApiResponse:
        if method == "GET" and path == "/api/bootstrap":
            return _json(
                200,
                {
                    "entries": [get_entry(item) for item in entry_ids()],
                    "sessions": list_sessions(self.root),
                    "capabilities": load_capabilities(self.root),
                },
            )

        parts = [part for part in path.split("/") if part]
        if method == "POST" and parts == ["api", "sessions"]:
            data = _parse_json(body)
            session_id = require_identifier(data["session_id"], "session_id")
            start_session(
                self.root,
                session_id,
                data["entry_id"],
                data["anchor"],
                self.clock(),
            )
            return _json(201, self._session_snapshot(session_id))

        if len(parts) >= 3 and parts[:2] == ["api", "sessions"]:
            session_id = require_identifier(parts[2], "session_id")
            if method == "GET" and len(parts) == 3:
                return _json(200, self._session_snapshot(session_id))
            if method == "POST" and parts[3:] == ["answers"]:
                data = _parse_json(body)
                if data.get("skip") is True:
                    skip_question(
                        self.root,
                        session_id,
                        data["question_id"],
                        self.clock(),
                    )
                else:
                    answer_question(
                        self.root,
                        session_id,
                        data["question_id"],
                        data["answer"],
                        self.clock(),
                    )
                return _json(200, self._session_snapshot(session_id))
            if method == "POST" and parts[3:] == ["pause"]:
                pause_session(self.root, session_id, self.clock())
                return _json(200, self._session_snapshot(session_id))
            if method == "POST" and parts[3:] == ["resume"]:
                resume_session(self.root, session_id, self.clock())
                return _json(200, self._session_snapshot(session_id))
            if method == "POST" and parts[3:] == ["complete"]:
                complete_session(self.root, session_id, self.clock())
                build_local_projection(self.root, session_id, self.clock())
                return _json(201, self._session_snapshot(session_id))
            if method == "PATCH" and parts[3:] == ["card"]:
                update_card_copy(
                    self.root,
                    session_id,
                    _parse_json(body),
                    self.clock(),
                )
                return _json(200, load_projection(self.root, session_id))
            if method == "POST" and parts[3:] == ["privacy-reviews"]:
                data = _parse_json(body)
                review_id = require_identifier(data["review_id"], "review_id")
                review_path = create_privacy_review(
                    self.root,
                    session_id,
                    review_id,
                    data["fields"],
                    data["redactions"],
                    self.clock(),
                )
                return _json(201, load_json_preserving_corrupt(review_path))
            if (
                method == "POST"
                and len(parts) == 6
                and parts[3] == "privacy-reviews"
                and parts[5] == "confirm"
            ):
                review_id = require_identifier(parts[4], "review_id")
                review_path = confirm_privacy_review(
                    self.root,
                    session_id,
                    review_id,
                    self.clock(),
                )
                return _json(200, load_json_preserving_corrupt(review_path))
            if method == "POST" and parts[3:] == ["jobs"]:
                data = _parse_json(body)
                job_id = require_identifier(data["job_id"], "job_id")
                create_job(
                    self.root,
                    job_id,
                    session_id,
                    data["kind"],
                    data["privacy_review_id"],
                    self.clock(),
                )
                return _json(201, get_job(self.root, job_id))
            if (
                method == "POST"
                and parts[3:] == ["card-export"]
                and content_type == "image/png"
            ):
                saved = save_card_png(self.root, session_id, body, self.clock())
                return _json(201, {"filename": saved.name})

        if (
            method == "GET"
            and len(parts) == 4
            and parts[:2] == ["api", "jobs"]
            and parts[3] == "asset"
        ):
            job = get_job(self.root, require_identifier(parts[2], "job_id"))
            if job["status"] != "completed" or job["kind"] != "image_background":
                raise FileNotFoundError("completed image job not found")
            stored_image = Path(job["result"]["image_path"]).resolve()
            relative_image = stored_image.relative_to(self.root.resolve())
            image = resolve_within(self.root, relative_image)
            if image.parent != (self.root / "outputs" / "images").resolve():
                raise ValueError("image is outside outputs/images")
            content_type = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }[image.suffix.lower()]
            return ApiResponse(200, image.read_bytes(), content_type)
        if method == "GET" and len(parts) == 3 and parts[:2] == ["api", "jobs"]:
            return _json(
                200,
                get_job(self.root, require_identifier(parts[2], "job_id")),
            )
        return _json(404, {"error": "not_found"})
