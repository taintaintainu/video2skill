"""Compact generated-skill artifacts and replay verification contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(value, encoding="utf-8")
    os.replace(tmp, path)


def _step_id(chunk_id: str, subtask_index: int, step_index: int) -> str:
    return f"{chunk_id}:s{subtask_index:02d}:p{step_index:03d}"


def build_source_index(
    fine_chunks: list[dict[str, Any]], trajectory: dict[str, Any]
) -> dict[str, Any]:
    """Index source steps without repeating the complete annotation payload."""
    retained_as: dict[str, set[str]] = {}
    canonical_count = 0
    for subtask in trajectory.get("subtasks", []):
        for step in subtask.get("steps", []):
            canonical_count += 1
            canonical = str(step.get("source_step_id") or f"canonical-{canonical_count:04d}")
            for source_id in {
                canonical,
                *[str(value) for value in step.get("merged_source_step_ids", [])],
                *[str(value) for value in step.get("replaces_broad_step_ids", [])],
            }:
                retained_as.setdefault(source_id, set()).add(canonical)

    steps: dict[str, dict[str, Any]] = {}
    for chunk in sorted(fine_chunks, key=lambda item: float(item["chunk_start_sec"])):
        chunk_id = str(chunk["chunk_id"])
        for subtask_index, subtask in enumerate(chunk.get("subtasks", [])):
            for step_index, step in enumerate(subtask.get("steps", [])):
                source_id = _step_id(chunk_id, subtask_index, step_index)
                retained = sorted(retained_as.get(source_id, set()))
                record: dict[str, Any] = {
                    "chunk_id": chunk_id,
                    "start_sec": float(step["start_sec"]),
                    "end_sec": float(step["end_sec"]),
                    "retained_as": retained,
                }
                # Canonical details already live in semantic_trajectory.json. Repeat a small
                # semantic hint only for dropped/replaced source records that cannot be looked up
                # directly in the authoritative trajectory.
                if retained != [source_id]:
                    record["interaction_type"] = str(step.get("interaction_type") or "")
                    record["target"] = str(step.get("target") or "")
                steps[source_id] = record
    return {
        "schema_version": "source_index_v1",
        "source_step_count": len(steps),
        "canonical_step_count": canonical_count,
        "steps": steps,
    }


_MANUAL_REVIEW = re.compile(
    r"\b(delete|remove|erase|uninstall|publish|post|send|email|message|submit|"
    r"purchase|buy|pay|transfer|upload|install|sign[ -]?in|log[ -]?in|password|"
    r"credential|api[ -]?key|token|grant|permission|share)\b|"
    r"删除|移除|卸载|发布|发送|提交|购买|支付|转账|上传|安装|登录|密码|凭据|"
    r"密钥|令牌|授权|权限|共享",
    re.IGNORECASE,
)


def build_verification_manifest(trajectory: dict[str, Any]) -> dict[str, Any]:
    """Describe a safe computer-use replay check without claiming it already ran."""
    manual_review_steps = []
    manual = 0
    ordinal = 0
    for subtask in trajectory.get("subtasks", []):
        for step in subtask.get("steps", []):
            ordinal += 1
            source_id = str(step.get("source_step_id") or f"canonical-{ordinal:04d}")
            text = " ".join(
                str(step.get(field) or "")
                for field in (
                    "action_description",
                    "target",
                    "typed_value_or_hotkey",
                    "visible_result",
                )
            )
            reasons = []
            if "<redacted-sensitive-value>" in text:
                reasons.append("redacted value requires an authorized replacement")
            if _MANUAL_REVIEW.search(text):
                reasons.append("potentially consequential action")
            status = "manual_review" if reasons else "pending"
            if status == "manual_review":
                manual += 1
                item: dict[str, Any] = {
                    "source_step_id": source_id,
                    "reasons": reasons,
                }
                if step.get("evidence_frame"):
                    item["evidence_frame"] = str(step["evidence_frame"])
                manual_review_steps.append(item)
    return {
        "schema_version": "replay_verification_v1",
        "status": "unverified",
        "trajectory_sha256": stable_hash(trajectory),
        "policy": {
            "executor": "computer-use",
            "environment": "user-approved disposable sandbox",
            "backup_required": True,
            "network": "deny unless the demonstrated workflow requires it and the user authorizes it",
            "manual_review_behavior": "stop before acting and request user authorization",
            "success_rule": "verify each step against visible_result; never infer success",
        },
        "summary": {
            "total": ordinal,
            "pending": ordinal,
            "manual_review": manual,
            "verified": 0,
        },
        "manual_review_steps": manual_review_steps,
        "results": {},
    }
