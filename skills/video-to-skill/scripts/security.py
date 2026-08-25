"""Artifact redaction and media-evidence safety checks."""

from __future__ import annotations

import re
from typing import Any


_SENSITIVE_FIELD = re.compile(
    r"password|passcode|secret|api[ _-]?key|access[ _-]?key|token|credential|"
    r"private[ _-]?key|client[ _-]?secret|密码|口令|密钥|令牌|凭据|私钥|邮箱|邮件地址|身份证",
    re.IGNORECASE,
)
_SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|rk|pk)-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.IGNORECASE),
    re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
        r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?"
        r"-----END [A-Z0-9 ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_REDACTED = "<redacted-sensitive-value>"
_AUDIO_CLAIM = re.compile(
    r"\b(narrator|speaker|voice[ -]?over|spoken|audio says|says aloud)\b|"
    r"旁白|讲解者|解说|语音|口头说明|声音中",
    re.IGNORECASE,
)


def _redact_embedded_secrets(text: str, *, redact_email: bool = False) -> tuple[str, int]:
    redacted = text
    count = 0
    patterns = (*_SECRET_PATTERNS, _EMAIL) if redact_email else _SECRET_PATTERNS
    for pattern in patterns:
        redacted, replaced = pattern.subn(_REDACTED, redacted)
        count += replaced
    return redacted, count


def redact_sensitive_values(value: dict[str, Any], *, allow: bool = False) -> int:
    """Remove likely credentials and personal identifiers before artifacts are cached."""
    if allow:
        return 0
    count = 0
    if isinstance(value.get("summary"), str):
        value["summary"], replaced = _redact_embedded_secrets(value["summary"])
        count += replaced
    for subtask in value.get("subtasks", []):
        for step in subtask.get("steps", []):
            context = " ".join(
                str(step.get(field) or "")
                for field in ("action_description", "target", "visible_result")
            )
            typed = str(step.get("typed_value_or_hotkey") or "")
            scrubbed, replaced = _redact_embedded_secrets(
                typed, redact_email=bool(_SENSITIVE_FIELD.search(context))
            )
            if _SENSITIVE_FIELD.search(context) and typed and scrubbed == typed:
                scrubbed, replaced = _REDACTED, 1
            step["typed_value_or_hotkey"] = scrubbed
            count += replaced
            for field in ("action_description", "visible_result"):
                if isinstance(step.get(field), str):
                    step[field], replaced = _redact_embedded_secrets(step[field])
                    count += replaced
    for note in value.get("context_notes", []):
        context = " ".join(str(note.get(field) or "") for field in ("note", "evidence"))
        redact_email = bool(_SENSITIVE_FIELD.search(context))
        for field in ("note", "evidence"):
            if isinstance(note.get(field), str):
                note[field], replaced = _redact_embedded_secrets(
                    note[field], redact_email=redact_email
                )
                count += replaced
    if count:
        value.setdefault("quality_flags", []).append(
            {"code": "sensitive_values_redacted", "count": count}
        )
    return count


def enforce_media_evidence(
    value: dict[str, Any], *, audio_present: bool, audio_available_to_model: bool
) -> None:
    """Drop audio-attributed notes when the provider request cannot support them."""
    if audio_present and audio_available_to_model:
        return
    kept = []
    removed = 0
    for note in value.get("context_notes", []):
        text = " ".join((str(note.get("note") or ""), str(note.get("evidence") or "")))
        if _AUDIO_CLAIM.search(text):
            removed += 1
            continue
        kept.append(note)
    value["context_notes"] = kept
    if removed:
        value.setdefault("quality_flags", []).append(
            {"code": "unsupported_audio_claim_removed", "count": removed}
        )
