"""Inference-provider adapters for Video2Skill.

Seed and Gemini receive video proxy chunks. OpenAI (including the ``codex`` API
alias) and generic OpenAI-compatible endpoints receive locally sampled JPEG
frames because the default OpenAI model accepts image, but not video, input.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any

from core import (
    FINE_SCHEMA,
    Chunk,
    MediaTooLargeError,
    PipelineConfig,
    SeedClient,
    extract_output_text,
    fine_prompt,
    normalize_chunk_timestamps,
    normalize_fine,
    run_checked,
    validate_fine,
)
from http_transport import (
    HTTPTransportError,
    is_retryable as _retryable,
    request_json as _request_json,
    retry_delay as _retry_delay,
)
from security import enforce_media_evidence, redact_sensitive_values


DEFAULT_MODELS = {
    "seed": "doubao-seed-2-1-turbo-260628",
    "gemini": "gemini-2.5-pro",
    "openai": "gpt-5.6-sol",
    "codex": "gpt-5.6-sol",
}

DEFAULT_BASE_URLS = {
    "seed": "https://ark.cn-beijing.volces.com/api/plan/v3",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "openai": "https://api.openai.com/v1",
    "codex": "https://api.openai.com/v1",
}

DEFAULT_KEY_ENVS = {
    "seed": "ARK_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "codex": "OPENAI_API_KEY",
    "openai-compatible": "OPENAI_COMPATIBLE_API_KEY",
}


ProviderHTTPError = HTTPTransportError


def _json_text(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    return json.loads(cleaned)


class GeminiClient:
    provider_name = "gemini"
    audio_available_to_model = True

    def __init__(self, config: PipelineConfig, api_key: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required")
        self.config = config
        self.api_key = api_key

    def cache_identity(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.config.model,
            "base_url": self.config.base_url,
            "fps": self.config.fps,
            "inline_bytes": self.config.inline_bytes,
            "allow_sensitive_values": self.config.allow_sensitive_values,
        }

    @staticmethod
    def extract_text(response: dict[str, Any]) -> str:
        texts: list[str] = []
        for candidate in response.get("candidates", []):
            content = candidate.get("content") or {}
            for part in content.get("parts", []):
                if isinstance(part, dict) and part.get("text"):
                    texts.append(str(part["text"]))
        return "\n".join(texts)

    def _generate(
        self, parts: list[dict[str, Any]], schema: dict[str, Any], schema_name: str
    ) -> dict[str, Any]:
        del schema_name  # Gemini accepts the schema itself, not a schema name.
        url = (
            f"{self.config.base_url.rstrip('/')}/models/"
            f"{self.config.model}:generateContent"
        )
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        last: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                return _request_json(
                    "POST",
                    url,
                    {"x-goog-api-key": self.api_key},
                    payload,
                    self.config.timeout_seconds,
                )
            except Exception as exc:
                last = exc
                message = str(exc).casefold()
                if isinstance(exc, ProviderHTTPError) and (
                    exc.status == 413
                    or (
                        exc.status in {400, 422}
                        and any(term in message for term in ("too large", "request size", "payload size"))
                    )
                ):
                    raise MediaTooLargeError(str(exc)) from exc
                if attempt >= self.config.retries or not _retryable(exc):
                    raise
                time.sleep(_retry_delay(exc, attempt, self.config.retry_base_seconds))
        raise RuntimeError(str(last))

    def response(
        self, content: list[dict[str, Any]], schema: dict[str, Any], schema_name: str
    ) -> dict[str, Any]:
        parts = [
            {"text": str(item.get("text") or "")}
            for item in content
            if item.get("type") == "input_text"
        ]
        return self._generate(parts, schema, schema_name)

    def analyze_chunk(
        self, video: Path, chunk: Chunk, media_info: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        prompt = fine_prompt(
            bool(media_info.get("has_audio")), self.audio_available_to_model
        )
        encoded_video_bytes = 4 * ((video.stat().st_size + 2) // 3)
        estimated_request_bytes = (
            encoded_video_bytes
            + len(prompt.encode("utf-8"))
            + len(json.dumps(FINE_SCHEMA).encode("utf-8"))
            + 8192
        )
        if estimated_request_bytes >= self.config.inline_bytes:
            raise MediaTooLargeError(
                f"Gemini inline request estimate {estimated_request_bytes} exceeds "
                f"{self.config.inline_bytes} bytes"
            )
        mime = mimetypes.guess_type(video.name)[0] or "video/mp4"
        parts = [
            {
                "inlineData": {
                    "mimeType": mime,
                    "data": base64.b64encode(video.read_bytes()).decode("ascii"),
                }
            },
            {
                "text": prompt
            },
        ]
        raw = self._generate(parts, FINE_SCHEMA, "semantic_trajectory_v2")
        value = _json_text(self.extract_text(raw))
        normalize_fine(value)
        redact_sensitive_values(value, allow=self.config.allow_sensitive_values)
        enforce_media_evidence(
            value,
            audio_present=bool(media_info.get("has_audio")),
            audio_available_to_model=self.audio_available_to_model,
        )
        normalize_chunk_timestamps(value, chunk)
        value["chunk_id"] = chunk.chunk_id
        value["chunk_start_sec"] = chunk.start_sec
        value["chunk_end_sec"] = chunk.end_sec
        validate_fine(value, allow_empty_subtasks=True)
        return value, raw


class OpenAICompatibleClient:
    audio_available_to_model = False

    def __init__(
        self,
        config: PipelineConfig,
        api_key: str,
        *,
        provider_name: str,
        api_mode: str = "responses",
        frame_fps: float = 0.5,
        max_frames: int = 60,
        structured_output: str = "auto",
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        no_auth: bool = False,
    ) -> None:
        if not api_key and not no_auth:
            raise ValueError("An API key is required")
        if api_mode not in {"responses", "chat-completions"}:
            raise ValueError("api_mode must be responses or chat-completions")
        if structured_output not in {"auto", "json-schema", "prompt"}:
            raise ValueError("structured_output must be auto, json-schema, or prompt")
        if frame_fps <= 0 or max_frames < 1:
            raise ValueError("frame_fps and max_frames must be positive")
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", auth_header):
            raise ValueError("auth_header is not a valid HTTP header name")
        if any(ord(char) < 32 for char in auth_scheme):
            raise ValueError("auth_scheme contains control characters")
        self.config = config
        self.api_key = api_key
        self.provider_name = provider_name
        self.api_mode = api_mode
        self.frame_fps = frame_fps
        self.max_frames = max_frames
        self.structured_output = structured_output
        self.auth_header = auth_header
        self.auth_scheme = auth_scheme
        self.no_auth = no_auth

    def cache_identity(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.config.model,
            "base_url": self.config.base_url,
            "api_mode": self.api_mode,
            "frame_fps": self.frame_fps,
            "max_frames": self.max_frames,
            "structured_output": self.structured_output,
            "allow_sensitive_values": self.config.allow_sensitive_values,
            "auth_header": self.auth_header,
            "auth_scheme": self.auth_scheme,
            "auth_mode": "none" if self.no_auth else "header",
        }

    def extract_text(self, response: dict[str, Any]) -> str:
        if self.api_mode == "responses":
            return extract_output_text(response)
        texts: list[str] = []
        for choice in response.get("choices", []):
            content = (choice.get("message") or {}).get("content")
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("text"):
                        texts.append(str(part["text"]))
        return "\n".join(texts)

    def _endpoint(self) -> str:
        suffix = "responses" if self.api_mode == "responses" else "chat/completions"
        return f"{self.config.base_url.rstrip('/')}/{suffix}"

    def _send_once(
        self,
        content: list[dict[str, Any]],
        schema: dict[str, Any],
        schema_name: str,
        *,
        strict: bool,
        include_store: bool,
    ) -> dict[str, Any]:
        if self.api_mode == "responses":
            payload: dict[str, Any] = {
                "model": self.config.model,
                "input": [{"role": "user", "content": content}],
            }
            if include_store:
                payload["store"] = False
            if strict:
                payload["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    }
                }
        else:
            chat_content: list[dict[str, Any]] = []
            for item in content:
                if item.get("type") == "input_text":
                    chat_content.append({"type": "text", "text": item.get("text", "")})
                elif item.get("type") == "input_image":
                    chat_content.append({
                        "type": "image_url",
                        "image_url": {"url": item["image_url"], "detail": item.get("detail", "auto")},
                    })
            payload = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": chat_content}],
            }
            if strict:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    },
                }
        headers = {}
        if not self.no_auth:
            credential = (
                f"{self.auth_scheme} {self.api_key}" if self.auth_scheme else self.api_key
            )
            headers[self.auth_header] = credential
        return _request_json(
            "POST",
            self._endpoint(),
            headers,
            payload,
            self.config.timeout_seconds,
        )

    def _send(
        self, content: list[dict[str, Any]], schema: dict[str, Any], schema_name: str
    ) -> dict[str, Any]:
        strict = self.structured_output != "prompt"
        include_store = self.api_mode == "responses"
        if not strict:
            content = [
                *content,
                {
                    "type": "input_text",
                    "text": "Return only JSON matching this schema:\n" + json.dumps(schema),
                },
            ]
        last: Exception | None = None
        attempt = 0
        while attempt <= self.config.retries:
            try:
                return self._send_once(
                    content,
                    schema,
                    schema_name,
                    strict=strict,
                    include_store=include_store,
                )
            except ProviderHTTPError as exc:
                body = exc.body.casefold()
                if exc.status == 413 or (
                    exc.status in {400, 422}
                    and any(term in body for term in ("too large", "max message tokens", "image tokens"))
                ):
                    raise MediaTooLargeError(str(exc)) from exc
                if (
                    include_store
                    and self.provider_name in {"openai-compatible", "local"}
                    and exc.status in {400, 422}
                    and "store" in body
                ):
                    include_store = False
                    continue
                schema_rejected = any(
                    term in body
                    for term in ("json_schema", "response_format", "structured output", "text.format")
                )
                if (
                    strict
                    and self.structured_output == "auto"
                    and exc.status in {400, 404, 422}
                    and schema_rejected
                ):
                    strict = False
                    content = [
                        *content,
                        {
                            "type": "input_text",
                            "text": "Return only JSON matching this schema:\n" + json.dumps(schema),
                        },
                    ]
                    continue
                last = exc
            except Exception as exc:
                last = exc
            if attempt >= self.config.retries or not _retryable(last):
                raise last  # type: ignore[misc]
            time.sleep(_retry_delay(last, attempt, self.config.retry_base_seconds))
            attempt += 1
        raise RuntimeError(str(last))

    def response(
        self, content: list[dict[str, Any]], schema: dict[str, Any], schema_name: str
    ) -> dict[str, Any]:
        return self._send(content, schema, schema_name)

    def _extract_frames(self, video: Path, duration: float, destination: Path) -> list[Path]:
        effective_fps = min(self.frame_fps, self.max_frames / max(duration, 0.001))
        run_checked([
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"fps={effective_fps:g},scale=-2:min({self.config.max_video_height}\\,ih)",
            "-frames:v",
            str(self.max_frames),
            "-q:v",
            "4",
            str(destination / "frame-%04d.jpg"),
        ])
        return sorted(destination.glob("frame-*.jpg"))

    def analyze_chunk(
        self, video: Path, chunk: Chunk, media_info: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        duration = chunk.end_sec - chunk.start_sec
        with tempfile.TemporaryDirectory(prefix="video2skill-frames-") as temp_dir:
            frames = self._extract_frames(video, duration, Path(temp_dir))
            if not frames:
                raise RuntimeError("ffmpeg produced no frames")
            interval = duration / max(len(frames), 1)
            content: list[dict[str, Any]] = [{
                "type": "input_text",
                "text": fine_prompt(
                    bool(media_info.get("has_audio")), self.audio_available_to_model
                )
                + f"\nThe clip is represented by {len(frames)} ordered sampled frames, "
                f"approximately {interval:.3f} seconds apart. Use the supplied frame labels "
                "for approximate clip-relative timestamps.",
            }]
            for index, frame in enumerate(frames):
                timestamp = min(duration, index * interval)
                content.append({
                    "type": "input_text",
                    "text": f"Frame {index + 1}/{len(frames)} at approximately {timestamp:.3f}s",
                })
                content.append({
                    "type": "input_image",
                    "image_url": "data:image/jpeg;base64,"
                    + base64.b64encode(frame.read_bytes()).decode("ascii"),
                    "detail": "high",
                })
            raw = self._send(content, FINE_SCHEMA, "semantic_trajectory_v2")

        value = _json_text(self.extract_text(raw))
        normalize_fine(value)
        redact_sensitive_values(value, allow=self.config.allow_sensitive_values)
        enforce_media_evidence(
            value,
            audio_present=bool(media_info.get("has_audio")),
            audio_available_to_model=self.audio_available_to_model,
        )
        normalize_chunk_timestamps(value, chunk)
        value["chunk_id"] = chunk.chunk_id
        value["chunk_start_sec"] = chunk.start_sec
        value["chunk_end_sec"] = chunk.end_sec
        value.setdefault("quality_flags", []).append({
            "code": "sampled_frames_no_audio",
            "frame_count": len(frames),
            "approx_interval_seconds": round(interval, 3),
        })
        validate_fine(value, allow_empty_subtasks=True)
        return value, raw


def create_provider(
    provider: str,
    *,
    model: str | None,
    base_url: str | None,
    api_key_env: str | None,
    api_mode: str,
    frame_fps: float,
    max_frames: int,
    structured_output: str,
    timeout_seconds: int,
    retries: int,
    chunk_max_seconds: float,
    chunk_overlap_seconds: float,
    max_video_height: int,
    delete_remote_files: bool,
    allow_sensitive_values: bool = False,
    auth_header: str = "Authorization",
    auth_scheme: str = "Bearer",
    no_auth: bool = False,
) -> Any:
    normalized = provider.casefold().strip()
    if normalized not in {
        "seed", "gemini", "openai", "codex", "openai-compatible", "local"
    }:
        raise ValueError(f"Unsupported provider: {provider}")
    if no_auth and normalized not in {"openai-compatible", "local"}:
        raise ValueError("--no-auth applies only to local or openai-compatible providers")
    resolved_model = model or DEFAULT_MODELS.get(normalized)
    if not resolved_model:
        raise ValueError(f"--model is required for provider {normalized}")

    resolved_base_url = base_url or DEFAULT_BASE_URLS.get(normalized)
    if not resolved_base_url:
        raise ValueError(f"--base-url is required for provider {normalized}")
    parsed_base = urllib.parse.urlparse(resolved_base_url)
    if parsed_base.username or parsed_base.password:
        raise ValueError("Credentials must not be embedded in --base-url")
    if parsed_base.query or parsed_base.fragment:
        raise ValueError("--base-url must not contain query parameters or fragments")
    if not parsed_base.hostname or any(ord(char) < 32 for char in resolved_base_url):
        raise ValueError("--base-url is invalid")
    loopback = parsed_base.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed_base.scheme != "https" and not (parsed_base.scheme == "http" and loopback):
        raise ValueError("--base-url must use HTTPS; HTTP is allowed only for loopback endpoints")
    no_auth = no_auth or normalized == "local"
    if no_auth and not loopback:
        raise ValueError("Unauthenticated endpoints are allowed only on loopback addresses")
    if no_auth:
        if api_key_env:
            raise ValueError("--api-key-env cannot be combined with --no-auth or --provider local")
        api_key = ""
    else:
        key_env = api_key_env or DEFAULT_KEY_ENVS[normalized]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key_env):
            raise ValueError("--api-key-env must be a valid environment-variable name")
        api_key = os.getenv(key_env)
        if not api_key:
            raise ValueError(f"Environment variable {key_env} is required")

    if normalized == "seed":
        config = PipelineConfig(
            model=resolved_model,
            base_url=resolved_base_url,
            timeout_seconds=timeout_seconds,
            retries=retries,
            chunk_max_seconds=chunk_max_seconds,
            chunk_overlap_seconds=chunk_overlap_seconds,
            max_video_height=max_video_height,
            delete_remote_files=delete_remote_files,
            allow_sensitive_values=allow_sensitive_values,
        )
        return SeedClient(config, api_key, os.getenv("ARK_FILES_API_KEY"))

    inline_bytes = 20 * 1024 * 1024 if normalized == "gemini" else 50 * 1024 * 1024
    config = PipelineConfig(
        model=resolved_model,
        base_url=resolved_base_url,
        timeout_seconds=timeout_seconds,
        retries=retries,
        chunk_max_seconds=chunk_max_seconds,
        chunk_overlap_seconds=chunk_overlap_seconds,
        max_video_height=max_video_height,
        inline_bytes=inline_bytes,
        delete_remote_files=delete_remote_files,
        allow_sensitive_values=allow_sensitive_values,
    )
    if normalized == "gemini":
        return GeminiClient(config, api_key)
    return OpenAICompatibleClient(
        config,
        api_key,
        provider_name=(
            "codex-api" if normalized == "codex" else normalized
        ),
        api_mode=api_mode,
        frame_fps=frame_fps,
        max_frames=max_frames,
        structured_output=structured_output,
        auth_header=auth_header if normalized == "openai-compatible" else "Authorization",
        auth_scheme=auth_scheme if normalized == "openai-compatible" else "Bearer",
        no_auth=no_auth,
    )
