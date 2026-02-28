#!/usr/bin/env python3
"""Example: chat with Puter AI using token or temporary browser guest auth."""

from __future__ import annotations

import os
import sys

from puter_ai import PuterAIClient


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Say hello in one short sentence."

    token = os.getenv("PUTER_AUTH_TOKEN")
    allow_temp_guest = os.getenv("PUTER_ALLOW_TEMP_GUEST", "0") == "1"
    temp_guest_per_request = os.getenv("PUTER_TEMP_GUEST_PER_REQUEST", "0") == "1"

    if not token and not allow_temp_guest:
        print(
            "Error: set PUTER_AUTH_TOKEN or enable PUTER_ALLOW_TEMP_GUEST=1.",
            file=sys.stderr,
        )
        return 2

    client = PuterAIClient(
        api_base_url=os.getenv("PUTER_API_BASE_URL", "https://api.puter.com"),
        gui_origin=os.getenv("PUTER_GUI_ORIGIN", "https://puter.com"),
        token=token,
        allow_temp_guest=allow_temp_guest,
        temp_guest_per_request=temp_guest_per_request,
    )

    model = os.getenv("PUTER_MODEL")
    result = client.chat(prompt, model=model)
    print(result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
