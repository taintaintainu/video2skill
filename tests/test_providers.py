from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "video-to-skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import providers
from core import FINE_SCHEMA, SeedConfig


class ProviderTests(unittest.TestCase):
    def test_gemini_payload_uses_video_capable_generate_content(self) -> None:
        config = SeedConfig(model="gemini-test", base_url="https://gemini.invalid/v1beta", retries=0)
        client = providers.GeminiClient(config, "secret")
        with patch.object(providers, "_request_json", return_value={"candidates": []}) as request:
            client.response(
                [{"type": "input_text", "text": "merge"}],
                FINE_SCHEMA,
                "trajectory",
            )
        url = request.call_args.args[1]
        headers = request.call_args.args[2]
        payload = request.call_args.args[3]
        self.assertEqual(url, "https://gemini.invalid/v1beta/models/gemini-test:generateContent")
        self.assertEqual(headers["x-goog-api-key"], "secret")
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(payload["generationConfig"]["responseSchema"], FINE_SCHEMA)

    def test_openai_responses_payload_disables_storage(self) -> None:
        config = SeedConfig(model="gpt-test", base_url="https://api.invalid/v1", retries=0)
        client = providers.OpenAICompatibleClient(
            config, "secret", provider_name="openai", api_mode="responses"
        )
        with patch.object(providers, "_request_json", return_value={"output": []}) as request:
            client.response(
                [{"type": "input_text", "text": "merge"}],
                FINE_SCHEMA,
                "trajectory",
            )
        payload = request.call_args.args[3]
        self.assertFalse(payload["store"])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertEqual(request.call_args.args[1], "https://api.invalid/v1/responses")

    def test_chat_completions_payload(self) -> None:
        config = SeedConfig(model="local-model", base_url="http://localhost:9000/v1", retries=0)
        client = providers.OpenAICompatibleClient(
            config,
            "secret",
            provider_name="openai-compatible",
            api_mode="chat-completions",
        )
        with patch.object(providers, "_request_json", return_value={"choices": []}) as request:
            client.response(
                [{"type": "input_text", "text": "merge"}],
                FINE_SCHEMA,
                "trajectory",
            )
        payload = request.call_args.args[3]
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(request.call_args.args[1], "http://localhost:9000/v1/chat/completions")

    def test_auto_mode_falls_back_when_json_schema_is_unsupported(self) -> None:
        config = SeedConfig(model="local-model", base_url="http://localhost:9000/v1", retries=0)
        client = providers.OpenAICompatibleClient(
            config,
            "secret",
            provider_name="openai-compatible",
            structured_output="auto",
        )
        calls = []

        def fake_request(method, url, headers, payload, timeout):
            del method, url, headers, timeout
            calls.append(payload)
            if len(calls) == 1:
                raise providers.ProviderHTTPError(
                    400, "http://localhost", "json_schema unsupported"
                )
            return {"output": []}

        with patch.object(providers, "_request_json", side_effect=fake_request):
            client.response(
                [{"type": "input_text", "text": "merge"}],
                FINE_SCHEMA,
                "trajectory",
            )
        self.assertIn("text", calls[0])
        self.assertNotIn("text", calls[1])
        fallback_text = calls[1]["input"][0]["content"][-1]["text"]
        self.assertIn("Return only JSON matching this schema", fallback_text)

    def test_create_provider_never_requires_key_on_command_line(self) -> None:
        with patch.dict(os.environ, {"CUSTOM_KEY": "secret"}, clear=False):
            client = providers.create_provider(
                "openai-compatible",
                model="model",
                base_url="http://localhost:9000/v1",
                api_key_env="CUSTOM_KEY",
                api_mode="responses",
                frame_fps=0.5,
                max_frames=10,
                structured_output="auto",
                timeout_seconds=30,
                retries=0,
                chunk_max_seconds=60,
                chunk_overlap_seconds=5,
                max_video_height=720,
                delete_remote_files=True,
            )
        self.assertEqual(client.provider_name, "openai-compatible")
        self.assertNotIn("secret", json.dumps(client.cache_identity()))

    def test_local_provider_allows_loopback_without_a_key(self) -> None:
        client = providers.create_provider(
            "local",
            model="vision",
            base_url="http://127.0.0.1:9000/v1",
            api_key_env=None,
            api_mode="chat-completions",
            frame_fps=0.5,
            max_frames=10,
            structured_output="auto",
            timeout_seconds=30,
            retries=0,
            chunk_max_seconds=60,
            chunk_overlap_seconds=5,
            max_video_height=720,
            delete_remote_files=True,
        )
        self.assertEqual(client.provider_name, "local")
        self.assertEqual(client.cache_identity()["auth_mode"], "none")
        with patch.object(providers, "_request_json", return_value={"choices": []}) as request:
            client.response(
                [{"type": "input_text", "text": "merge"}],
                FINE_SCHEMA,
                "trajectory",
            )
        self.assertEqual(request.call_args.args[2], {})

    def test_no_auth_is_rejected_for_remote_endpoint(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            providers.create_provider(
                "openai-compatible",
                model="vision",
                base_url="https://provider.example/v1",
                api_key_env=None,
                api_mode="responses",
                frame_fps=0.5,
                max_frames=10,
                structured_output="auto",
                timeout_seconds=30,
                retries=0,
                chunk_max_seconds=60,
                chunk_overlap_seconds=5,
                max_video_height=720,
                delete_remote_files=True,
                no_auth=True,
            )

    def test_remote_plain_http_endpoint_is_rejected(self) -> None:
        with patch.dict(os.environ, {"CUSTOM_KEY": "secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "must use HTTPS"):
                providers.create_provider(
                    "openai-compatible",
                    model="model",
                    base_url="http://provider.example/v1",
                    api_key_env="CUSTOM_KEY",
                    api_mode="responses",
                    frame_fps=0.5,
                    max_frames=10,
                    structured_output="auto",
                    timeout_seconds=30,
                    retries=0,
                    chunk_max_seconds=60,
                    chunk_overlap_seconds=5,
                    max_video_height=720,
                    delete_remote_files=True,
                )

    def test_base_url_query_credentials_are_rejected(self) -> None:
        with patch.dict(os.environ, {"CUSTOM_KEY": "secret"}, clear=False):
            with self.assertRaisesRegex(ValueError, "query parameters"):
                providers.create_provider(
                    "openai-compatible",
                    model="model",
                    base_url="https://provider.example/v1?api_key=secret",
                    api_key_env="CUSTOM_KEY",
                    api_mode="responses",
                    frame_fps=0.5,
                    max_frames=10,
                    structured_output="auto",
                    timeout_seconds=30,
                    retries=0,
                    chunk_max_seconds=60,
                    chunk_overlap_seconds=5,
                    max_video_height=720,
                    delete_remote_files=True,
                )

    def test_custom_raw_credential_header(self) -> None:
        config = SeedConfig(model="local", base_url="https://api.invalid/v1", retries=0)
        client = providers.OpenAICompatibleClient(
            config,
            "secret",
            provider_name="openai-compatible",
            auth_header="api-key",
            auth_scheme="",
        )
        with patch.object(providers, "_request_json", return_value={"output": []}) as request:
            client.response(
                [{"type": "input_text", "text": "merge"}],
                FINE_SCHEMA,
                "trajectory",
            )
        self.assertEqual(request.call_args.args[2], {"api-key": "secret"})

    def test_compatible_responses_can_fall_back_without_store(self) -> None:
        config = SeedConfig(model="local", base_url="https://api.invalid/v1", retries=0)
        client = providers.OpenAICompatibleClient(
            config, "secret", provider_name="openai-compatible"
        )
        payloads = []

        def fake_request(method, url, headers, payload, timeout):
            del method, url, headers, timeout
            payloads.append(payload)
            if len(payloads) == 1:
                raise providers.ProviderHTTPError(400, "https://api.invalid", "unknown field store")
            return {"output": []}

        with patch.object(providers, "_request_json", side_effect=fake_request):
            client.response(
                [{"type": "input_text", "text": "merge"}],
                FINE_SCHEMA,
                "trajectory",
            )
        self.assertIn("store", payloads[0])
        self.assertNotIn("store", payloads[1])

    def test_gemini_uses_encoded_request_size_for_inline_limit(self) -> None:
        config = SeedConfig(
            model="gemini-test",
            base_url="https://gemini.invalid/v1beta",
            retries=0,
            inline_bytes=1024,
        )
        client = providers.GeminiClient(config, "secret")
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "chunk.mp4"
            video.write_bytes(b"x" * 900)
            with self.assertRaises(providers.MediaTooLargeError):
                client.analyze_chunk(
                    video,
                    providers.Chunk("chunk_000", 0.0, 10.0),
                    {"has_audio": False},
                )

    def test_non_retryable_auth_error_is_not_retried(self) -> None:
        config = SeedConfig(model="local", base_url="https://api.invalid/v1", retries=3)
        client = providers.OpenAICompatibleClient(
            config, "secret", provider_name="openai-compatible"
        )
        with patch.object(
            providers,
            "_request_json",
            side_effect=providers.ProviderHTTPError(401, "https://api.invalid", "unauthorized"),
        ) as request:
            with self.assertRaises(providers.ProviderHTTPError):
                client.response(
                    [{"type": "input_text", "text": "merge"}],
                    FINE_SCHEMA,
                    "trajectory",
                )
        self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
