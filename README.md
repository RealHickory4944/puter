# puter-ai-chat

A tiny Python library for chatting with Puter AI via the same backend path used by `puter.ai.chat(...)` in `@heyputer/puter.js`.

## Install

```bash
pip install -e .
```

## Quick start (with token)

```python
from puter_ai import PuterAIClient

client = PuterAIClient(token="YOUR_PUTER_AUTH_TOKEN")
result = client.chat("Write a 1-line haiku about coding.", model="gpt-5-nano")
print(result["text"])
```

## Quick start (temporary guest via browser)

```python
from puter_ai import PuterAIClient

client = PuterAIClient(allow_temp_guest=True)
result = client.chat("Hello from a temporary account")
print(result["text"])
```

This mode opens a browser login flow with temporary-user creation enabled, then captures the token via localhost callback.

## How this maps to puter.js

This client calls:

- `POST /drivers/call`
- body:
  - `interface: "puter-chat-completion"`
  - `driver: "ai-chat"`
  - `method: "complete"`
  - `args: { messages, model?, stream?, ... }`
  - `auth_token: <token>`

which mirrors the SDK implementation in `@heyputer/puter.js`.

## Auth modes

1. **Token mode** (recommended)
   - pass `token="..."`
2. **Temporary guest mode**
   - set `allow_temp_guest=True`
   - optionally set `temp_guest_per_request=True` to force a fresh browser flow every request

> Important: no client can guarantee "infinite free" usage. Rotating temporary users may still be limited by Puter-side abuse/rate/funding controls.

## Runnable example

Token mode:

```bash
PUTER_AUTH_TOKEN=... PYTHONPATH=src python examples/chat_with_token.py "Say hello"
```

Temporary guest mode (browser popup flow):

```bash
PUTER_ALLOW_TEMP_GUEST=1 PYTHONPATH=src python examples/chat_with_token.py "Say hello"
```

Override API / GUI origins (useful for local/self-hosted):

```bash
PUTER_API_BASE_URL=http://127.0.0.1:8080 PUTER_GUI_ORIGIN=http://puter.localhost:4100 PUTER_ALLOW_TEMP_GUEST=1 PYTHONPATH=src python examples/chat_with_token.py "Test"
```
