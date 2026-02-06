"""Tests for Augment hooks."""

from datetime import datetime

from augment_agent_memory.hooks.session_start import build_context
from augment_agent_memory.hooks.stop import extract_messages_from_conversation


class TestBuildContext:
    """Tests for build_context function.

    Note: build_context signature is (workspace_summary, session_summary, memories)
    """

    def test_build_context_with_all(self):
        """Test building context with workspace summary, session summary, and memories."""
        workspace_summary = "User works on microservices."
        session_summary = "Current focus on Redis integration."
        memories = ["Favorite language is Python", "Works on backend systems"]

        result = build_context(workspace_summary, session_summary, memories)

        assert "## Workspace Context" in result
        assert "microservices" in result
        assert "## Session Context" in result
        assert "Redis integration" in result
        assert "## Relevant Memories" in result
        assert "1. Favorite language is Python" in result
        assert "2. Works on backend systems" in result

    def test_build_context_with_workspace_summary_only(self):
        """Test building context with only workspace summary."""
        result = build_context("Workspace info.", None, [])

        assert "## Workspace Context" in result
        assert "Workspace info." in result
        assert "## Session Context" not in result
        assert "## Relevant Memories" not in result

    def test_build_context_with_session_summary_only(self):
        """Test building context with only session summary."""
        result = build_context(None, "Session info.", [])

        assert "## Workspace Context" not in result
        assert "## Session Context" in result
        assert "Session info." in result

    def test_build_context_with_only_memories(self):
        """Test building context with only memories."""
        memories = ["Memory 1", "Memory 2"]

        result = build_context(None, None, memories)

        assert "## Workspace Context" not in result
        assert "## Session Context" not in result
        assert "## Relevant Memories" in result
        assert "1. Memory 1" in result

    def test_build_context_empty(self):
        """Test building context with no data."""
        result = build_context(None, None, [])
        assert result == ""


class TestExtractMessages:
    """Tests for extract_messages_from_conversation function."""

    def test_extract_full_conversation(self):
        """Test extracting messages from complete conversation data."""
        conversation = {
            "userPrompt": "How do I use Redis?",
            "agentTextResponse": "Redis is an in-memory data store...",
        }

        messages = extract_messages_from_conversation(conversation)

        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "How do I use Redis?"
        assert messages[1].role == "assistant"
        assert messages[1].content == "Redis is an in-memory data store..."

    def test_extract_user_only(self):
        """Test extracting messages with only user prompt."""
        conversation = {
            "userPrompt": "Hello",
        }

        messages = extract_messages_from_conversation(conversation)

        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "Hello"

    def test_extract_code_response(self):
        """Test extracting messages with code response instead of text."""
        conversation = {
            "userPrompt": "Show me code",
            "agentCodeResponse": "print('hello')",
        }

        messages = extract_messages_from_conversation(conversation)

        assert len(messages) == 2
        assert messages[1].role == "assistant"
        assert messages[1].content == "print('hello')"

    def test_extract_combines_text_and_code(self):
        """Test that text and code responses are combined."""
        conversation = {
            "userPrompt": "Question",
            "agentTextResponse": "Text answer",
            "agentCodeResponse": "code_answer()",
        }

        messages = extract_messages_from_conversation(conversation)

        assert len(messages) == 2
        # Both text and code are included in the response
        assert "Text answer" in messages[1].content
        assert "code_answer()" in messages[1].content

    def test_extract_empty_conversation(self):
        """Test extracting from empty conversation."""
        messages = extract_messages_from_conversation({})
        assert len(messages) == 0

    def test_messages_have_timestamps(self):
        """Test that extracted messages have timestamps."""
        conversation = {
            "userPrompt": "Test",
            "agentTextResponse": "Response",
        }

        messages = extract_messages_from_conversation(conversation)

        for msg in messages:
            assert msg.created_at is not None
            assert isinstance(msg.created_at, datetime)

