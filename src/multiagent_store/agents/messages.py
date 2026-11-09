"""Shared message helpers."""


def message_text(message) -> str:
    c = message.content
    if isinstance(c, str):
        return c
    return "".join(b.get("text", "") for b in c if isinstance(b, dict))
