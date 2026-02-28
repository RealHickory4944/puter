import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _MockPuterHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(content_length).decode("utf-8"))

        if self.path == "/drivers/call":
            assert body["interface"] == "puter-chat-completion"
            assert body["driver"] == "ai-chat"
            assert body["method"] == "complete"
            payload = {"success": True, "result": {"message": {"content": "mocked assistant reply"}}}
        else:
            self.send_response(404)
            self.end_headers()
            return

        response_body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, format, *args):
        return


class ExampleScriptTests(unittest.TestCase):
    def test_chat_example_script(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _MockPuterHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            repo_root = Path(__file__).resolve().parents[1]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(repo_root / "src")
            env["PUTER_API_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
            env["PUTER_AUTH_TOKEN"] = "tok_test"

            run = subprocess.run(
                [
                    sys.executable,
                    str(repo_root / "examples" / "chat_with_token.py"),
                    "Hello from test",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertIn("mocked assistant reply", run.stdout)


if __name__ == "__main__":
    unittest.main()
