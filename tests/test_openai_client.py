from __future__ import annotations

import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

fake_openai = types.ModuleType("openai")


class DummyOpenAI:
    def __init__(self, *args, **kwargs) -> None:
        self.responses = None


fake_openai.OpenAI = DummyOpenAI
fake_openai.error = types.SimpleNamespace()
sys.modules.setdefault("openai", fake_openai)

from reformulator import openai_client as module


class ExtractRewrittenHtmlTests(unittest.TestCase):
    def test_prefers_structured_json_payload(self) -> None:
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    content=[
                        SimpleNamespace(json={"rewritten_html": "<p>OK</p>"}, text=None)
                    ]
                )
            ]
        )
        self.assertEqual(module.extract_rewritten_html(response), "<p>OK</p>")

    def test_parses_json_string_when_needed(self) -> None:
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    content=[
                        SimpleNamespace(json=None, text='{"rewritten_html": "<div>Alt</div>"}')
                    ]
                )
            ]
        )
        self.assertEqual(module.extract_rewritten_html(response), "<div>Alt</div>")


class StubResponses:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):  # type: ignore[override]
        self.calls.append(kwargs)
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    content=[
                        SimpleNamespace(json={"rewritten_html": "<p>Réécrit</p>"}, text=None)
                    ]
                )
            ]
        )


class StubClient:
    def __init__(self) -> None:
        self.responses = StubResponses()


class CallOpenAITests(unittest.TestCase):
    def test_returns_rewritten_result(self) -> None:
        client = StubClient()
        previous = module.USE_RESPONSE_FORMAT
        try:
            module.USE_RESPONSE_FORMAT = True
            result = module.call_openai(client, "gpt-test", "<p>Source</p>", max_retries=1)
        finally:
            module.USE_RESPONSE_FORMAT = previous
        self.assertEqual(result, "<p>Réécrit</p>")
        self.assertEqual(client.responses.calls[0]["model"], "gpt-test")
        self.assertIn("input", client.responses.calls[0])


class CreateClientTests(unittest.TestCase):
    def test_raises_when_env_missing(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(EnvironmentError):
                module.create_client()


if __name__ == "__main__":
    unittest.main()
