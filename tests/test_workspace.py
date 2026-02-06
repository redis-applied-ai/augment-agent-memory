"""Tests for workspace utilities."""

from augment_agent_memory.workspace import (
    get_persistent_session_id,
    get_session_summary_view_name,
    get_workspace_id,
    get_workspace_name,
    get_workspace_namespace,
    get_workspace_root,
    get_workspace_summary_view_name,
)


class TestGetWorkspaceRoot:
    """Tests for get_workspace_root function."""

    def test_returns_first_workspace(self):
        """Test that it returns the first workspace from the list."""
        result = get_workspace_root(["/path/to/project", "/other/path"])
        assert result == "/path/to/project"

    def test_returns_none_for_empty_list(self):
        """Test that it returns cwd for empty list."""
        result = get_workspace_root([])
        # Falls back to cwd
        assert result is not None

    def test_returns_cwd_for_none(self):
        """Test that it returns cwd for None input."""
        result = get_workspace_root(None)
        assert result is not None


class TestGetWorkspaceId:
    """Tests for get_workspace_id function."""

    def test_returns_stable_id(self):
        """Test that same path returns same ID."""
        id1 = get_workspace_id("/path/to/project")
        id2 = get_workspace_id("/path/to/project")
        assert id1 == id2

    def test_different_paths_different_ids(self):
        """Test that different paths return different IDs."""
        id1 = get_workspace_id("/path/to/project1")
        id2 = get_workspace_id("/path/to/project2")
        assert id1 != id2

    def test_returns_8_char_hex(self):
        """Test that ID is 8 hex characters."""
        result = get_workspace_id("/path/to/project")
        assert len(result) == 8
        assert all(c in "0123456789abcdef" for c in result)


class TestGetWorkspaceName:
    """Tests for get_workspace_name function."""

    def test_returns_directory_name(self):
        """Test that it returns the directory name."""
        result = get_workspace_name("/path/to/my-project")
        assert result == "my-project"

    def test_handles_trailing_slash(self):
        """Test that it handles trailing slashes."""
        result = get_workspace_name("/path/to/project/")
        assert result == "project"


class TestGetWorkspaceNamespace:
    """Tests for get_workspace_namespace function."""

    def test_combines_base_and_workspace(self):
        """Test that it combines base namespace with workspace name."""
        result = get_workspace_namespace("augment", "/path/to/my-project")
        assert result == "augment:my-project"

    def test_sanitizes_special_chars(self):
        """Test that special characters are sanitized."""
        result = get_workspace_namespace("base", "/path/to/my project!")
        assert result == "base:my_project_"


class TestGetPersistentSessionId:
    """Tests for get_persistent_session_id function."""

    def test_with_conversation_id(self):
        """Test session ID with conversation ID."""
        result = get_persistent_session_id("/path/to/project", "conv-123")
        assert result == "augment:project:conv-123"

    def test_without_conversation_id(self):
        """Test session ID without conversation ID."""
        result = get_persistent_session_id("/path/to/project", None)
        assert result.startswith("augment:project:")
        # Should end with workspace ID (8 hex chars)
        suffix = result.split(":")[-1]
        assert len(suffix) == 8


class TestGetWorkspaceSummaryViewName:
    """Tests for get_workspace_summary_view_name function."""

    def test_generates_view_name(self):
        """Test that it generates a valid view name."""
        result = get_workspace_summary_view_name("/path/to/my-project")
        assert result == "augment_workspace_my-project"


class TestGetSessionSummaryViewName:
    """Tests for get_session_summary_view_name function."""

    def test_generates_view_name(self):
        """Test that it generates a valid view name."""
        result = get_session_summary_view_name("/path/to/project", "session-123")
        assert result.startswith("augment_session_project_")
        # Should include session hash (8 hex chars)
        suffix = result.split("_")[-1]
        assert len(suffix) == 8

    def test_different_sessions_different_names(self):
        """Test that different sessions get different view names."""
        name1 = get_session_summary_view_name("/path/to/project", "session-1")
        name2 = get_session_summary_view_name("/path/to/project", "session-2")
        assert name1 != name2

