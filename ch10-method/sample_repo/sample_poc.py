"""sample_poc.py — a POC skeleton in the house pattern.

Fill in the pure core, keep the edge isolated, drive the seam with a fake in tests.
"""

from __future__ import annotations

from typing import Callable, Optional

# The injectable seam: the one step that could call a model/network. Fake it in tests.
Caller = Callable[[str], str]


def build_prompt(task: str) -> str:
    """PURE: turn input into a request. No I/O."""
    return f"Do this task: {task}"


def parse_response(text: str) -> str:
    """PURE: turn a raw response into your result type. No I/O."""
    return text.strip()


def run(task: str, *, caller: Caller) -> str:
    """PURE wiring over the seam: build -> call(seam) -> parse."""
    prompt = build_prompt(task)
    raw = caller(prompt)
    return parse_response(raw)


def _call_model(prompt: str) -> str:
    """IMPURE EDGE: import the SDK LOCALLY so the module imports offline."""
    import anthropic  # local import: no key/SDK needed to import this file

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


if __name__ == "__main__":
    import sys

    task = " ".join(sys.argv[1:]) or "say hello"
    print(run(task, caller=_call_model))
