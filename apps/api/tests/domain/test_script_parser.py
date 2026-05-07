"""Unit tests for ``app.domain.voice.script_parser``."""

from __future__ import annotations

from app.domain.voice.script_parser import QAPair, ScriptParsed, parse_script


def test_parse_script_full_document() -> None:
    """A complete script populates every section."""
    content = """## Opening Pitch
Hello there.
Welcome to the demo.

## Q&A
Q: What is your pricing?
A: Starts at $10/mo.

Q: Do you offer a free trial?
A: Yes, 14 days.

## Fallback
Let me get back to you on that.

## Scheduling
Would tomorrow at 3pm work?
"""
    result = parse_script(content)

    assert isinstance(result, ScriptParsed)
    assert "Hello there." in result.opening_pitch
    assert "Welcome to the demo." in result.opening_pitch
    assert result.fallback_response == "Let me get back to you on that."
    assert result.scheduling_question == "Would tomorrow at 3pm work?"
    assert len(result.qa_pairs) == 2
    assert result.qa_pairs[0].question == "What is your pricing?"
    assert result.qa_pairs[0].answer == "Starts at $10/mo."
    assert result.qa_pairs[1].question == "Do you offer a free trial?"
    assert result.qa_pairs[1].answer == "Yes, 14 days."


def test_parse_script_empty_content() -> None:
    """Empty content yields default empty ScriptParsed."""
    result = parse_script("")
    assert result.opening_pitch == ""
    assert result.fallback_response == ""
    assert result.scheduling_question == ""
    assert result.qa_pairs == []


def test_parse_script_unknown_sections_ignored() -> None:
    """Headers we don't recognize are skipped silently."""
    content = """## Random Section
some text

## Opening Pitch
Hi
"""
    result = parse_script(content)
    assert result.opening_pitch == "Hi"
    assert result.fallback_response == ""


def test_parse_script_case_insensitive_headers() -> None:
    """Headers are matched case-insensitively."""
    content = """## OPENING PITCH
Greetings

## fallback
ok
"""
    result = parse_script(content)
    assert result.opening_pitch == "Greetings"
    assert result.fallback_response == "ok"


def test_parse_script_qa_with_multi_line_answer() -> None:
    """Answer lines that follow A: continuation are concatenated."""
    content = """## Q&A
Q: Tell me more
A: First line
Second line continuation

Q: Another?
A: Short
"""
    result = parse_script(content)
    assert len(result.qa_pairs) == 2
    assert "First line" in result.qa_pairs[0].answer
    assert "Second line continuation" in result.qa_pairs[0].answer
    assert result.qa_pairs[1].answer == "Short"


def test_parse_script_qa_lowercase_prefix() -> None:
    """Q:/A: matching is case-insensitive on the prefix."""
    content = """## Q&A
q: lowercase question
a: lowercase answer
"""
    result = parse_script(content)
    assert len(result.qa_pairs) == 1
    assert result.qa_pairs[0].question == "lowercase question"
    assert result.qa_pairs[0].answer == "lowercase answer"


def test_parse_script_qa_orphan_question_dropped() -> None:
    """A question without an A: line is not emitted."""
    content = """## Q&A
Q: orphan with no answer
"""
    result = parse_script(content)
    assert result.qa_pairs == []


def test_parse_script_qa_orphan_continuation_lines_ignored() -> None:
    """Lines before any A: are not collected as answers."""
    content = """## Q&A
random line before any Q
Q: real q
A: real a
"""
    result = parse_script(content)
    assert len(result.qa_pairs) == 1
    assert result.qa_pairs[0].answer == "real a"


def test_parse_script_section_with_only_whitespace() -> None:
    """Section with only blank lines yields empty string after strip."""
    content = """## Opening Pitch


## Fallback
end
"""
    result = parse_script(content)
    assert result.opening_pitch == ""
    assert result.fallback_response == "end"


def test_parse_script_no_headers_yields_empty() -> None:
    """Plain text without headers produces empty ScriptParsed."""
    result = parse_script("just some narrative text without any markdown")
    assert result.opening_pitch == ""
    assert result.qa_pairs == []


def test_qapair_is_dataclass() -> None:
    """QAPair stores question and answer fields."""
    pair = QAPair(question="q", answer="a")
    assert pair.question == "q"
    assert pair.answer == "a"
