"""Tests for Augment hooks."""

import io
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from augment_agent_memory.hooks.post_tool_use import (
    format_tool_usage,
)
from augment_agent_memory.hooks.post_tool_use import (
    run_hook as post_tool_run,
)
from augment_agent_memory.hooks.session_start import (
    build_context,
    ensure_summary_view_exists,
    get_summary_context,
    search_relevant_memories,
)
from augment_agent_memory.hooks.session_start import (
    run_hook as session_start_run,
)
from augment_agent_memory.hooks.stop import (
    extract_messages_from_conversation,
)
from augment_agent_memory.hooks.stop import (
    run_hook as stop_run,
)


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


class TestFormatToolUsage:
    """Tests for format_tool_usage function."""

    def test_format_launch_process(self):
        """Test formatting launch-process tool usage."""
        hook_input = {
            "tool_name": "launch-process",
            "tool_input": {"command": "pytest -v"},
        }
        result = format_tool_usage(hook_input)
        assert result is not None
        assert "launch-process" in result
        assert "pytest -v" in result

    def test_format_str_replace_editor(self):
        """Test formatting str-replace-editor tool usage."""
        hook_input = {
            "tool_name": "str-replace-editor",
            "tool_input": {"path": "src/main.py"},
        }
        result = format_tool_usage(hook_input)
        assert result is not None
        assert "str-replace-editor" in result
        assert "src/main.py" in result

    def test_format_github_api(self):
        """Test formatting github-api tool usage."""
        hook_input = {
            "tool_name": "github-api",
            "tool_input": {"path": "/repos/owner/repo/pulls", "method": "POST"},
        }
        result = format_tool_usage(hook_input)
        assert result is not None
        assert "GitHub: POST /repos/owner/repo/pulls" in result

    def test_format_with_file_changes(self):
        """Test formatting with file changes."""
        hook_input = {
            "tool_name": "save-file",
            "tool_input": {"path": "new_file.py"},
            "file_changes": [
                {"changeType": "create", "path": "new_file.py"},
            ],
        }
        result = format_tool_usage(hook_input)
        assert result is not None
        assert "create: new_file.py" in result

    def test_format_with_error(self):
        """Test formatting with tool error."""
        hook_input = {
            "tool_name": "launch-process",
            "tool_input": {"command": "failing-cmd"},
            "tool_error": "Command not found",
        }
        result = format_tool_usage(hook_input)
        assert result is not None
        assert "Error: Command not found" in result

    def test_skip_view_tool(self):
        """Test that view tool is skipped."""
        hook_input = {"tool_name": "view", "tool_input": {}}
        result = format_tool_usage(hook_input)
        assert result is None

    def test_skip_codebase_retrieval(self):
        """Test that codebase-retrieval tool is skipped."""
        hook_input = {"tool_name": "codebase-retrieval", "tool_input": {}}
        result = format_tool_usage(hook_input)
        assert result is None

    def test_skip_web_search(self):
        """Test that web-search tool is skipped."""
        hook_input = {"tool_name": "web-search", "tool_input": {}}
        result = format_tool_usage(hook_input)
        assert result is None


class TestEnsureSummaryViewExists:
    """Tests for ensure_summary_view_exists function."""

    @pytest.mark.asyncio
    async def test_returns_existing_view_id(self):
        """Test that existing view ID is returned."""
        mock_client = AsyncMock()
        mock_view = MagicMock()
        mock_view.name = "test_view"
        mock_view.id = "view-123"
        mock_client.list_summary_views.return_value = [mock_view]

        result = await ensure_summary_view_exists(mock_client, "test_view", ["namespace"])

        assert result == "view-123"
        mock_client.create_summary_view.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new_view(self):
        """Test that new view is created when not found."""
        mock_client = AsyncMock()
        mock_client.list_summary_views.return_value = []
        mock_created = MagicMock()
        mock_created.id = "new-view-456"
        mock_client.create_summary_view.return_value = mock_created

        result = await ensure_summary_view_exists(mock_client, "new_view", ["namespace"])

        assert result == "new-view-456"
        mock_client.create_summary_view.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        """Test that None is returned on error."""
        mock_client = AsyncMock()
        mock_client.list_summary_views.side_effect = Exception("API error")

        result = await ensure_summary_view_exists(mock_client, "test_view", ["namespace"])

        assert result is None


class TestGetSummaryContext:
    """Tests for get_summary_context function."""

    @pytest.mark.asyncio
    async def test_returns_summary(self):
        """Test that summary is returned from partition."""
        mock_client = AsyncMock()
        mock_partition = MagicMock()
        mock_partition.summary = "This is the summary content"
        mock_client.list_summary_view_partitions.return_value = [mock_partition]

        result = await get_summary_context(mock_client, "view-123", namespace="test")

        assert result == "This is the summary content"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_partitions(self):
        """Test that None is returned when no partitions exist."""
        mock_client = AsyncMock()
        mock_client.list_summary_view_partitions.return_value = []

        result = await get_summary_context(mock_client, "view-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_summary(self):
        """Test that None is returned when partition has no summary."""
        mock_client = AsyncMock()
        mock_partition = MagicMock()
        mock_partition.summary = None
        mock_client.list_summary_view_partitions.return_value = [mock_partition]

        result = await get_summary_context(mock_client, "view-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        """Test that None is returned on error."""
        mock_client = AsyncMock()
        mock_client.list_summary_view_partitions.side_effect = Exception("API error")

        result = await get_summary_context(mock_client, "view-123")

        assert result is None


class TestSearchRelevantMemories:
    """Tests for search_relevant_memories function."""

    @pytest.mark.asyncio
    async def test_returns_memory_texts(self):
        """Test that memory texts are returned."""
        mock_client = AsyncMock()
        mock_memory1 = MagicMock()
        mock_memory1.text = "Memory 1"
        mock_memory2 = MagicMock()
        mock_memory2.text = "Memory 2"
        mock_result = MagicMock()
        mock_result.memories = [mock_memory1, mock_memory2]
        mock_client.search_long_term_memory.return_value = mock_result

        result = await search_relevant_memories(mock_client, "test query")

        assert result == ["Memory 1", "Memory 2"]

    @pytest.mark.asyncio
    async def test_filters_empty_texts(self):
        """Test that empty texts are filtered out."""
        mock_client = AsyncMock()
        mock_memory1 = MagicMock()
        mock_memory1.text = "Memory 1"
        mock_memory2 = MagicMock()
        mock_memory2.text = None
        mock_memory3 = MagicMock()
        mock_memory3.text = ""
        mock_result = MagicMock()
        mock_result.memories = [mock_memory1, mock_memory2, mock_memory3]
        mock_client.search_long_term_memory.return_value = mock_result

        result = await search_relevant_memories(mock_client, "test query")

        assert result == ["Memory 1"]

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        """Test that empty list is returned on error."""
        mock_client = AsyncMock()
        mock_client.search_long_term_memory.side_effect = Exception("API error")

        result = await search_relevant_memories(mock_client, "test query")

        assert result == []


class TestExtractMessagesCodeChanges:
    """Tests for code change formatting in extract_messages_from_conversation."""

    def test_extract_code_changes_as_list(self):
        """Test extracting code changes when agentCodeResponse is a list."""
        conversation = {
            "userPrompt": "Make changes",
            "agentCodeResponse": [
                {"changeType": "edit", "path": "src/main.py"},
                {"changeType": "create", "path": "src/new.py"},
            ],
        }

        messages = extract_messages_from_conversation(conversation)

        assert len(messages) == 2
        assert "[edit: src/main.py]" in messages[1].content
        assert "[create: src/new.py]" in messages[1].content

    def test_extract_code_changes_with_text(self):
        """Test extracting both text and code changes."""
        conversation = {
            "userPrompt": "Question",
            "agentTextResponse": "Here are the changes:",
            "agentCodeResponse": [
                {"changeType": "edit", "path": "file.py"},
            ],
        }

        messages = extract_messages_from_conversation(conversation)

        assert "Here are the changes:" in messages[1].content
        assert "[edit: file.py]" in messages[1].content


class TestStopEnsureSummaryViewExists:
    """Tests for ensure_summary_view_exists in stop.py."""

    @pytest.mark.asyncio
    async def test_returns_existing_view_id(self):
        """Test that existing view ID is returned."""
        from augment_agent_memory.hooks.stop import (
            ensure_summary_view_exists as stop_ensure,
        )

        mock_client = AsyncMock()
        mock_view = MagicMock()
        mock_view.name = "test_view"
        mock_view.id = "view-123"
        mock_client.list_summary_views.return_value = [mock_view]

        result = await stop_ensure(mock_client, "test_view", ["namespace"])

        assert result == "view-123"

    @pytest.mark.asyncio
    async def test_creates_new_view(self):
        """Test that new view is created when not found."""
        from augment_agent_memory.hooks.stop import (
            ensure_summary_view_exists as stop_ensure,
        )

        mock_client = AsyncMock()
        mock_client.list_summary_views.return_value = []
        mock_created = MagicMock()
        mock_created.id = "new-view-456"
        mock_client.create_summary_view.return_value = mock_created

        result = await stop_ensure(mock_client, "new_view", ["namespace"])

        assert result == "new-view-456"

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        """Test that None is returned on error."""
        from augment_agent_memory.hooks.stop import (
            ensure_summary_view_exists as stop_ensure,
        )

        mock_client = AsyncMock()
        mock_client.list_summary_views.side_effect = Exception("API error")

        result = await stop_ensure(mock_client, "test_view", ["namespace"])

        assert result is None


class TestSessionStartRunHook:
    """Tests for session_start run_hook function."""

    @pytest.mark.asyncio
    async def test_run_hook_auto_recall_disabled(self):
        """Test that run_hook returns empty when auto_recall is disabled."""
        mock_config = MagicMock()
        mock_config.auto_recall = False
        mock_config.use_workspace_namespace = False
        mock_config.use_persistent_session = False
        mock_config.namespace = "test"

        hook_input = json.dumps({"workspace_roots": ["/test"], "conversation_id": "123"})

        with (
            patch("augment_agent_memory.hooks.session_start.load_config", return_value=mock_config),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await session_start_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_invalid_json(self):
        """Test that run_hook handles invalid JSON input."""
        mock_config = MagicMock()
        mock_config.auto_recall = False
        mock_config.use_workspace_namespace = False
        mock_config.use_persistent_session = False
        mock_config.namespace = "test"

        with (
            patch("augment_agent_memory.hooks.session_start.load_config", return_value=mock_config),
            patch("sys.stdin", io.StringIO("not valid json")),
            patch("builtins.print") as mock_print,
        ):
            await session_start_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_workspace_namespace(self):
        """Test that run_hook uses workspace namespace when enabled."""
        mock_config = MagicMock()
        mock_config.auto_recall = False
        mock_config.use_workspace_namespace = True
        mock_config.use_persistent_session = True
        mock_config.namespace = "base"

        hook_input = json.dumps({"workspace_roots": ["/test/project"], "conversation_id": "123"})

        with (
            patch("augment_agent_memory.hooks.session_start.load_config", return_value=mock_config),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await session_start_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_client_success(self):
        """Test run_hook with successful client interaction."""
        mock_config = MagicMock()
        mock_config.auto_recall = True
        mock_config.use_workspace_namespace = True
        mock_config.use_persistent_session = True
        mock_config.namespace = "base"
        mock_config.server_url = "http://localhost:8000"
        mock_config.timeout = 30000
        mock_config.create_workspace_summary = False
        mock_config.create_session_summary = False
        mock_config.recall_limit = 5
        mock_config.min_score = 0.3
        mock_config.summary_time_window_days = 30
        mock_config.user_id = "test-user"

        hook_input = json.dumps({"workspace_roots": ["/test/project"], "conversation_id": "123"})

        # Mock the client
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.memories = []
        mock_client.search_long_term_memory.return_value = mock_result

        # Create async context manager mock
        mock_client_class = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("augment_agent_memory.hooks.session_start.load_config", return_value=mock_config),
            patch("augment_agent_memory.hooks.session_start.MemoryAPIClient", mock_client_class),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await session_start_run()
            # No context means empty output
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_client_error(self):
        """Test run_hook handles client errors gracefully."""
        mock_config = MagicMock()
        mock_config.auto_recall = True
        mock_config.use_workspace_namespace = False
        mock_config.use_persistent_session = False
        mock_config.namespace = "test"
        mock_config.server_url = "http://localhost:8000"
        mock_config.timeout = 30000
        mock_config.create_workspace_summary = False
        mock_config.create_session_summary = False
        mock_config.recall_limit = 5
        mock_config.min_score = 0.3
        mock_config.summary_time_window_days = 30
        mock_config.user_id = None

        hook_input = json.dumps({"workspace_roots": ["/test"], "conversation_id": "123"})

        # Mock the client to raise an error
        mock_client = AsyncMock()
        mock_client.search_long_term_memory.side_effect = Exception("Connection error")

        mock_client_class = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("augment_agent_memory.hooks.session_start.load_config", return_value=mock_config),
            patch("augment_agent_memory.hooks.session_start.MemoryAPIClient", mock_client_class),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await session_start_run()
            # Should still output empty on error
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_summaries(self):
        """Test run_hook with workspace and session summaries enabled."""
        mock_config = MagicMock()
        mock_config.auto_recall = True
        mock_config.use_workspace_namespace = True
        mock_config.use_persistent_session = True
        mock_config.namespace = "base"
        mock_config.server_url = "http://localhost:8000"
        mock_config.timeout = 30000
        mock_config.create_workspace_summary = True
        mock_config.create_session_summary = True
        mock_config.recall_limit = 5
        mock_config.min_score = 0.3
        mock_config.summary_time_window_days = 30
        mock_config.user_id = "test-user"

        hook_input = json.dumps({"workspace_roots": ["/test/project"], "conversation_id": "123"})

        # Mock the client
        mock_client = AsyncMock()

        # Mock summary view exists
        mock_view = MagicMock()
        mock_view.name = "ws_summary"
        mock_view.id = "view-123"
        mock_client.list_summary_views.return_value = [mock_view]

        # Mock partition with summary
        mock_partition = MagicMock()
        mock_partition.summary = "Workspace summary content"
        mock_client.list_summary_view_partitions.return_value = [mock_partition]

        # Mock memory search
        mock_result = MagicMock()
        mock_memory = MagicMock()
        mock_memory.text = "A relevant memory"
        mock_result.memories = [mock_memory]
        mock_client.search_long_term_memory.return_value = mock_result

        mock_client_class = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("augment_agent_memory.hooks.session_start.load_config", return_value=mock_config),
            patch("augment_agent_memory.hooks.session_start.MemoryAPIClient", mock_client_class),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await session_start_run()
            # Should output context
            call_args = mock_print.call_args[0][0]
            assert "Workspace summary content" in call_args or "A relevant memory" in call_args


class TestStopRunHook:
    """Tests for stop run_hook function."""

    @pytest.mark.asyncio
    async def test_run_hook_auto_capture_disabled(self):
        """Test that run_hook returns empty when auto_capture is disabled."""
        mock_config = MagicMock()
        mock_config.auto_capture = False
        mock_config.use_workspace_namespace = False
        mock_config.use_persistent_session = False
        mock_config.namespace = "test"

        hook_input = json.dumps({
            "workspace_roots": ["/test"],
            "conversation_id": "123",
            "conversation": {"userPrompt": "test"},
        })

        with (
            patch("augment_agent_memory.hooks.stop.load_config", return_value=mock_config),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await stop_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_no_conversation(self):
        """Test that run_hook returns empty when no conversation data."""
        mock_config = MagicMock()
        mock_config.auto_capture = True
        mock_config.use_workspace_namespace = False
        mock_config.use_persistent_session = False
        mock_config.namespace = "test"

        hook_input = json.dumps({
            "workspace_roots": ["/test"],
            "conversation_id": "123",
            "conversation": {},
        })

        with (
            patch("augment_agent_memory.hooks.stop.load_config", return_value=mock_config),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await stop_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_invalid_json(self):
        """Test that run_hook handles invalid JSON input."""
        with (
            patch("sys.stdin", io.StringIO("not valid json")),
            patch("builtins.print") as mock_print,
        ):
            await stop_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_client_success(self):
        """Test run_hook with successful client interaction."""
        mock_config = MagicMock()
        mock_config.auto_capture = True
        mock_config.use_workspace_namespace = True
        mock_config.use_persistent_session = True
        mock_config.namespace = "base"
        mock_config.server_url = "http://localhost:8000"
        mock_config.timeout = 30000
        mock_config.create_workspace_summary = False
        mock_config.create_session_summary = False
        mock_config.user_id = "test-user"

        hook_input = json.dumps({
            "workspace_roots": ["/test/project"],
            "conversation_id": "123",
            "conversation": {
                "userPrompt": "Hello",
                "agentTextResponse": "Hi there!",
            },
        })

        # Mock the client
        mock_client = AsyncMock()

        mock_client_class = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("augment_agent_memory.hooks.stop.load_config", return_value=mock_config),
            patch("augment_agent_memory.hooks.stop.MemoryAPIClient", mock_client_class),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await stop_run()
            mock_client.append_messages_to_working_memory.assert_called_once()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_empty_messages(self):
        """Test run_hook when no messages are extracted."""
        mock_config = MagicMock()
        mock_config.auto_capture = True
        mock_config.use_workspace_namespace = False
        mock_config.use_persistent_session = False
        mock_config.namespace = "test"
        mock_config.server_url = "http://localhost:8000"
        mock_config.timeout = 30000

        hook_input = json.dumps({
            "workspace_roots": ["/test"],
            "conversation_id": "123",
            "conversation": {},  # Empty conversation
        })

        with (
            patch("augment_agent_memory.hooks.stop.load_config", return_value=mock_config),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await stop_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_summary_refresh(self):
        """Test run_hook with summary view refresh."""
        mock_config = MagicMock()
        mock_config.auto_capture = True
        mock_config.use_workspace_namespace = True
        mock_config.use_persistent_session = True
        mock_config.namespace = "base"
        mock_config.server_url = "http://localhost:8000"
        mock_config.timeout = 30000
        mock_config.create_workspace_summary = True
        mock_config.create_session_summary = True
        mock_config.user_id = "test-user"

        hook_input = json.dumps({
            "workspace_roots": ["/test/project"],
            "conversation_id": "123",
            "conversation": {
                "userPrompt": "Hello",
                "agentTextResponse": "Hi!",
            },
        })

        # Mock the client
        mock_client = AsyncMock()

        # Mock summary view exists
        mock_view = MagicMock()
        mock_view.name = "ws_summary"
        mock_view.id = "view-123"
        mock_client.list_summary_views.return_value = [mock_view]

        # Mock run_summary_view
        mock_task = MagicMock()
        mock_task.id = "task-456"
        mock_client.run_summary_view.return_value = mock_task

        mock_client_class = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("augment_agent_memory.hooks.stop.load_config", return_value=mock_config),
            patch("augment_agent_memory.hooks.stop.MemoryAPIClient", mock_client_class),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await stop_run()
            mock_client.append_messages_to_working_memory.assert_called_once()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_client_error(self):
        """Test run_hook handles client errors gracefully."""
        mock_config = MagicMock()
        mock_config.auto_capture = True
        mock_config.use_workspace_namespace = False
        mock_config.use_persistent_session = False
        mock_config.namespace = "test"
        mock_config.server_url = "http://localhost:8000"
        mock_config.timeout = 30000
        mock_config.create_workspace_summary = False
        mock_config.create_session_summary = False
        mock_config.user_id = None

        hook_input = json.dumps({
            "workspace_roots": ["/test"],
            "conversation_id": "123",
            "conversation": {
                "userPrompt": "Hello",
            },
        })

        # Mock the client to raise an error
        mock_client = AsyncMock()
        mock_client.append_messages_to_working_memory.side_effect = Exception("Connection error")

        mock_client_class = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("augment_agent_memory.hooks.stop.load_config", return_value=mock_config),
            patch("augment_agent_memory.hooks.stop.MemoryAPIClient", mock_client_class),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await stop_run()
            # Should still output empty on error
            mock_print.assert_called_with("{}")


class TestPostToolRunHook:
    """Tests for post_tool_use run_hook function."""

    @pytest.mark.asyncio
    async def test_run_hook_tracking_disabled(self):
        """Test that run_hook returns empty when tracking is disabled."""
        mock_config = MagicMock()
        mock_config.track_tool_usage = False

        with (
            patch("augment_agent_memory.hooks.post_tool_use.load_config", return_value=mock_config),
            patch("builtins.print") as mock_print,
        ):
            await post_tool_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_invalid_json(self):
        """Test that run_hook handles invalid JSON input."""
        mock_config = MagicMock()
        mock_config.track_tool_usage = True

        with (
            patch("augment_agent_memory.hooks.post_tool_use.load_config", return_value=mock_config),
            patch("sys.stdin", io.StringIO("not valid json")),
            patch("builtins.print") as mock_print,
        ):
            await post_tool_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_skipped_tool(self):
        """Test that run_hook returns empty for skipped tools."""
        mock_config = MagicMock()
        mock_config.track_tool_usage = True

        hook_input = json.dumps({"tool_name": "view", "tool_input": {}})

        with (
            patch("augment_agent_memory.hooks.post_tool_use.load_config", return_value=mock_config),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await post_tool_run()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_client_success(self):
        """Test run_hook with successful client interaction."""
        mock_config = MagicMock()
        mock_config.track_tool_usage = True
        mock_config.use_workspace_namespace = True
        mock_config.use_persistent_session = True
        mock_config.namespace = "base"
        mock_config.server_url = "http://localhost:8000"
        mock_config.timeout = 30000
        mock_config.user_id = "test-user"

        hook_input = json.dumps({
            "tool_name": "launch-process",
            "tool_input": {"command": "pytest"},
            "workspace_roots": ["/test/project"],
            "conversation_id": "123",
        })

        # Mock the client
        mock_client = AsyncMock()

        mock_client_class = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("augment_agent_memory.hooks.post_tool_use.load_config", return_value=mock_config),
            patch("augment_agent_memory.hooks.post_tool_use.MemoryAPIClient", mock_client_class),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await post_tool_run()
            mock_client.append_messages_to_working_memory.assert_called_once()
            mock_print.assert_called_with("{}")

    @pytest.mark.asyncio
    async def test_run_hook_with_client_error(self):
        """Test run_hook handles client errors gracefully."""
        mock_config = MagicMock()
        mock_config.track_tool_usage = True
        mock_config.use_workspace_namespace = False
        mock_config.use_persistent_session = False
        mock_config.namespace = "test"
        mock_config.server_url = "http://localhost:8000"
        mock_config.timeout = 30000
        mock_config.user_id = None

        hook_input = json.dumps({
            "tool_name": "save-file",
            "tool_input": {"path": "test.py"},
            "workspace_roots": ["/test"],
            "conversation_id": "123",
        })

        # Mock the client to raise an error
        mock_client = AsyncMock()
        mock_client.append_messages_to_working_memory.side_effect = Exception("Connection error")

        mock_client_class = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("augment_agent_memory.hooks.post_tool_use.load_config", return_value=mock_config),
            patch("augment_agent_memory.hooks.post_tool_use.MemoryAPIClient", mock_client_class),
            patch("sys.stdin", io.StringIO(hook_input)),
            patch("builtins.print") as mock_print,
        ):
            await post_tool_run()
            # Should still output empty on error
            mock_print.assert_called_with("{}")


class TestMainEntryPoints:
    """Tests for main() entry points."""

    def test_session_start_main(self):
        """Test session_start main entry point."""
        from augment_agent_memory.hooks.session_start import main as session_main

        mock_config = MagicMock()
        mock_config.auto_recall = False
        mock_config.use_workspace_namespace = False
        mock_config.use_persistent_session = False
        mock_config.namespace = "test"

        with (
            patch("augment_agent_memory.hooks.session_start.load_config", return_value=mock_config),
            patch("sys.stdin", io.StringIO("{}")),
            patch("builtins.print"),
        ):
            session_main()

    def test_stop_main(self):
        """Test stop main entry point."""
        from augment_agent_memory.hooks.stop import main as stop_main

        with (
            patch("sys.stdin", io.StringIO("{}")),
            patch("builtins.print"),
        ):
            stop_main()

    def test_post_tool_use_main(self):
        """Test post_tool_use main entry point."""
        from augment_agent_memory.hooks.post_tool_use import main as post_tool_main

        mock_config = MagicMock()
        mock_config.track_tool_usage = False

        with (
            patch("augment_agent_memory.hooks.post_tool_use.load_config", return_value=mock_config),
            patch("builtins.print"),
        ):
            post_tool_main()

