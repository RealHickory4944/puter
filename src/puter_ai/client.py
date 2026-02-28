"""Client for chatting with Puter.js-compatible AI endpoints from Python."""

from __future__ import annotations

import json
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, List, Optional
from urllib import error, request
from urllib.parse import quote_plus


@dataclass
class PuterAIClient:
    """
    Lightweight Python client modeled after ``puter.ai.chat(...)`` behavior.

    This client targets the same backend path used by puter.js:
    ``POST /drivers/call`` with:
      - ``interface`` = ``puter-chat-completion``
      - ``driver`` = ``ai-chat``
      - ``method`` = ``complete``

    Token behavior:
    - If ``token`` is provided, it is used directly.
    - If ``token`` is absent and ``allow_temp_guest=True``, the client can open
      a browser-based Puter login flow with temporary-user creation enabled and
      capture the returned token from a local callback URL.
    """

    api_base_url: str = "https://api.puter.com"
    gui_origin: str = "https://puter.com"
    token: Optional[str] = None
    timeout: int = 60

    drivers_call_endpoint: str = "/drivers/call"
    driver_interface: str = "puter-chat-completion"
    driver_name: str = "ai-chat"
    driver_method: str = "complete"

    allow_temp_guest: bool = False
    temp_guest_per_request: bool = False
    auth_timeout: int = 180

    _temp_guest_token: Optional[str] = None

    def _make_url(self, path: str) -> str:
        return f"{self.api_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _http_json(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        body = None
        merged_headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            merged_headers["Content-Type"] = "application/json"
        if headers:
            merged_headers.update(headers)

        req = request.Request(url=url, data=body, headers=merged_headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} calling {url}: {raw}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Network error calling {url}: {exc.reason}") from exc

        if not raw.strip():
            return {}

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Non-JSON response from {url}: {raw[:300]}") from exc

    def _get_auth_token(self) -> str:
        if self.token:
            return self.token

        if self.allow_temp_guest:
            if self.temp_guest_per_request or not self._temp_guest_token:
                self._temp_guest_token = self.create_temp_guest_token_via_browser()
            return self._temp_guest_token

        raise RuntimeError(
            "Puter auth token is required. Provide token=... or enable "
            "allow_temp_guest=True for browser-based temporary account auth."
        )

    def create_temp_guest_token_via_browser(self) -> str:
        """
        Open Puter sign-in in a browser with temporary user creation enabled.

        This mirrors puter.js sign-in behavior in spirit by using:
        ``/action/sign-in?...&attempt_temp_user_creation=true``
        and collecting the returned token from a localhost redirect.
        """
        token_holder: Dict[str, Optional[str]] = {"token": None}
        done = threading.Event()

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self_inner):
                token = None
                try:
                    if "?" in self_inner.path:
                        qs = self_inner.path.split("?", 1)[1]
                        for pair in qs.split("&"):
                            if not pair:
                                continue
                            key, _, value = pair.partition("=")
                            if key == "token":
                                token = value
                                break
                finally:
                    token_holder["token"] = token
                    done.set()

                body = (
                    "<html><body><h2>Puter auth complete</h2>"
                    "<p>You may now close this tab and return to your terminal.</p>"
                    "</body></html>"
                ).encode("utf-8")
                self_inner.send_response(200)
                self_inner.send_header("Content-Type", "text/html; charset=utf-8")
                self_inner.send_header("Content-Length", str(len(body)))
                self_inner.end_headers()
                self_inner.wfile.write(body)

            def log_message(self_inner, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), CallbackHandler)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            redirect = f"http://127.0.0.1:{port}"
            url = (
                f"{self.gui_origin.rstrip('/')}/action/sign-in"
                f"?embedded_in_popup=true"
                f"&attempt_temp_user_creation=true"
                f"&redirectURL={quote_plus(redirect)}"
            )
            opened = webbrowser.open(url)
            if not opened:
                raise RuntimeError(
                    "Could not automatically open browser. "
                    f"Open this URL manually:\n{url}"
                )

            if not done.wait(timeout=self.auth_timeout):
                raise RuntimeError(
                    "Timed out waiting for Puter browser auth callback. "
                    "Try again and complete login in the opened browser window."
                )

            token = token_holder.get("token")
            if not token:
                raise RuntimeError(
                    "Browser callback did not include token. "
                    "Puter may have changed redirect behavior."
                )

            return token
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def chat(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        messages: Optional[Iterable[Dict[str, Any]]] = None,
        stream: bool = False,
        extra_args: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a chat request through Puter's driver-call API.

        Returns a dictionary with:
          - ``text``: best-effort extracted model text
          - ``result``: result object from driver response when present
          - ``raw``: full JSON response
        """
        conversation: List[Dict[str, Any]] = []
        if system_prompt:
            conversation.append({"role": "system", "content": system_prompt})
        if messages:
            conversation.extend(messages)
        conversation.append({"role": "user", "content": prompt})

        args: Dict[str, Any] = {
            "messages": conversation,
            "stream": stream,
        }
        if model:
            args["model"] = model
        if provider:
            args["provider"] = provider
        if extra_args:
            args.update(extra_args)

        token = self._get_auth_token()
        payload: Dict[str, Any] = {
            "interface": self.driver_interface,
            "driver": self.driver_name,
            "method": self.driver_method,
            "args": args,
            "auth_token": token,
        }

        url = self._make_url(self.drivers_call_endpoint)
        raw = self._http_json("POST", url, payload=payload)

        if raw.get("success") is False:
            err = raw.get("error") or {}
            raise RuntimeError(f"Puter driver error: {err}")

        result = raw.get("result", raw)
        return {"text": self._extract_text(result), "result": result, "raw": raw}

    @staticmethod
    def _extract_text(result: Dict[str, Any]) -> str:
        message = result.get("message") if isinstance(result, dict) else None
        candidates = [
            result.get("text") if isinstance(result, dict) else None,
            result.get("content") if isinstance(result, dict) else None,
            message.get("content") if isinstance(message, dict) else None,
            (result.get("choices") or [{}])[0].get("message", {}).get("content")
            if isinstance(result, dict)
            and isinstance(result.get("choices"), list)
            and result.get("choices")
            else None,
        ]
        for item in candidates:
            if isinstance(item, str) and item.strip():
                return item

        return json.dumps(result, ensure_ascii=False)
