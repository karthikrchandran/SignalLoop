"""Parse markdown-style voice scripts into structured sections."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class QAPair:
    question: str
    answer: str


@dataclass
class ScriptParsed:
    opening_pitch: str = ""
    qa_pairs: list[QAPair] = field(default_factory=list)
    fallback_response: str = ""
    scheduling_question: str = ""


def parse_script(content: str) -> ScriptParsed:
    """Parse script content into structured sections.

    Expected format:
    ## Opening Pitch
    <text>

    ## Q&A
    Q: <question>
    A: <answer>

    ## Fallback
    <text>

    ## Scheduling
    <text>
    """
    result = ScriptParsed()
    sections: dict[str, str] = {}
    current_section = ""
    lines: list[str] = []

    for line in content.split("\n"):
        header_match = re.match(r"^##\s+(.+)$", line.strip())
        if header_match:
            if current_section:
                sections[current_section] = "\n".join(lines).strip()
            current_section = header_match.group(1).strip().lower()
            lines = []
        else:
            lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(lines).strip()

    result.opening_pitch = sections.get("opening pitch", "")
    result.fallback_response = sections.get("fallback", "")
    result.scheduling_question = sections.get("scheduling", "")

    # Parse Q&A section
    qa_text = sections.get("q&a", "")
    if qa_text:
        result.qa_pairs = _parse_qa_pairs(qa_text)

    return result


def _parse_qa_pairs(text: str) -> list[QAPair]:
    pairs: list[QAPair] = []
    current_q = ""
    current_a_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith("Q:"):
            if current_q and current_a_lines:
                pairs.append(QAPair(question=current_q, answer="\n".join(current_a_lines).strip()))
            current_q = stripped[2:].strip()
            current_a_lines = []
        elif stripped.upper().startswith("A:"):
            current_a_lines.append(stripped[2:].strip())
        elif current_a_lines:
            current_a_lines.append(stripped)

    if current_q and current_a_lines:
        pairs.append(QAPair(question=current_q, answer="\n".join(current_a_lines).strip()))

    return pairs
