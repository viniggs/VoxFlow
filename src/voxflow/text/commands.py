"""Deterministic spoken commands and snippet expansion."""

from __future__ import annotations

import re


def _delete_previous(text: str) -> str:
    pattern = re.compile(r"\b(?:apaga isso|esquece isso)\b", re.IGNORECASE)
    while match := pattern.search(text):
        before = text[: match.start()].rstrip(" ,")
        after = text[match.end() :].lstrip(" ,")
        boundary = max(before.rfind(mark) for mark in ".!?;\n")
        prefix = before[: boundary + 1].rstrip() if boundary >= 0 else ""
        text = " ".join(part for part in (prefix, after) if part)
    return text


def apply_spoken_commands(text: str) -> str:
    result = _delete_previous(text.strip())
    replacements = (
        (r"\bnovo parágrafo\b", "\n\n"),
        (r"\bnova linha\b", "\n"),
        (r"\bponto de interrogação\b|\binterrogação\b", "?"),
        (r"\bponto de exclamação\b|\bexclamação\b", "!"),
        (r"\bvírgula\b", ","),
        (r"\bponto\b", "."),
    )
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    result = re.sub(r"[ \t]+([,.!?])", r"\1", result)
    result = re.sub(r"[ \t]{2,}", " ", result)
    return result.strip()


def expand_snippets(text: str, snippets: dict[str, str]) -> str:
    result = text
    for trigger in sorted(snippets, key=len, reverse=True):
        replacement = snippets[trigger]
        result = re.sub(
            rf"(?<!\w){re.escape(trigger)}(?!\w)",
            lambda _, value=replacement: value,
            result,
            flags=re.IGNORECASE,
        )
    return result
