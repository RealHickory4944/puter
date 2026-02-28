import json
import unittest
from unittest.mock import patch

from puter_ai.client import PuterAIClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class PuterAIClientTests(unittest.TestCase):
    def test_chat_calls_drivers_call_with_puter_shape(self):
        sent_payloads = []

        def fake_urlopen(req, timeout=0):
            sent_payloads.append(json.loads(req.data.decode("utf-8")))
            return FakeResponse({"success": True, "result": {"message": {"content": "hello"}}})

        client = PuterAIClient(api_base_url="https://example.test", token="tok_123")
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.chat("Hi", model="gpt-5-nano")

        self.assertEqual(result["text"], "hello")
        self.assertEqual(sent_payloads[0]["interface"], "puter-chat-completion")
        self.assertEqual(sent_payloads[0]["driver"], "ai-chat")
        self.assertEqual(sent_payloads[0]["method"], "complete")
        self.assertEqual(sent_payloads[0]["auth_token"], "tok_123")
        self.assertEqual(sent_payloads[0]["args"]["messages"][0]["content"], "Hi")

    def test_chat_raises_when_token_missing_and_guest_disabled(self):
        client = PuterAIClient(api_base_url="https://example.test")
        with self.assertRaises(RuntimeError):
            client.chat("Hello")

    def test_chat_uses_temp_guest_when_enabled(self):
        sent_payloads = []

        def fake_urlopen(req, timeout=0):
            sent_payloads.append(json.loads(req.data.decode("utf-8")))
            return FakeResponse({"success": True, "result": {"message": {"content": "hello"}}})

        client = PuterAIClient(api_base_url="https://example.test", allow_temp_guest=True)
        with patch.object(client, "create_temp_guest_token_via_browser", return_value="guest_tok") as guest_mock:
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                client.chat("Hello")
                client.chat("Again")

        self.assertEqual(guest_mock.call_count, 1)
        self.assertEqual(sent_payloads[0]["auth_token"], "guest_tok")

    def test_chat_rotates_temp_guest_when_requested(self):
        sent_payloads = []

        def fake_urlopen(req, timeout=0):
            sent_payloads.append(json.loads(req.data.decode("utf-8")))
            return FakeResponse({"success": True, "result": {"message": {"content": "hello"}}})

        client = PuterAIClient(
            api_base_url="https://example.test",
            allow_temp_guest=True,
            temp_guest_per_request=True,
        )
        with patch.object(
            client,
            "create_temp_guest_token_via_browser",
            side_effect=["guest_tok_1", "guest_tok_2"],
        ) as guest_mock:
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                client.chat("One")
                client.chat("Two")

        self.assertEqual(guest_mock.call_count, 2)
        self.assertEqual(sent_payloads[0]["auth_token"], "guest_tok_1")
        self.assertEqual(sent_payloads[1]["auth_token"], "guest_tok_2")

    def test_chat_raises_driver_error(self):
        def fake_urlopen(req, timeout=0):
            return FakeResponse({"success": False, "error": {"code": "insufficient_funds"}})

        client = PuterAIClient(api_base_url="https://example.test", token="tok_123")
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(RuntimeError):
                client.chat("Hello")


if __name__ == "__main__":
    unittest.main()
