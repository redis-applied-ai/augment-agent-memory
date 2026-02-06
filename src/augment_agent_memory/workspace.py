"""Workspace utilities for session and namespace management."""

import hashlib
import os
from pathlib import Path


def get_workspace_root(workspace_roots: list[str] | None = None) -> str | None:
    """Get the primary workspace root from hook input or current directory.

    Args:
        workspace_roots: List of workspace roots from hook input.

    Returns:
        The primary workspace root path, or None if not determinable.
    """
    if workspace_roots and len(workspace_roots) > 0:
        return workspace_roots[0]
    # Fall back to current working directory
    return os.getcwd()


def get_workspace_id(workspace_root: str) -> str:
    """Generate a stable workspace ID from the workspace path.

    Creates a short hash-based ID that's stable across sessions.

    Args:
        workspace_root: The workspace root path.

    Returns:
        A short stable ID for the workspace (8 hex chars).
    """
    # Normalize the path
    normalized = os.path.normpath(os.path.abspath(workspace_root))
    # Create a stable hash
    hash_bytes = hashlib.sha256(normalized.encode()).digest()
    return hash_bytes[:4].hex()


def get_workspace_name(workspace_root: str) -> str:
    """Get a human-readable workspace name from the path.

    Args:
        workspace_root: The workspace root path.

    Returns:
        The workspace directory name (e.g., 'my-project').
    """
    return Path(workspace_root).name


def get_workspace_namespace(base_namespace: str, workspace_root: str) -> str:
    """Generate a workspace-specific namespace.

    Format: {base_namespace}:{workspace_name}

    Args:
        base_namespace: The base namespace from config.
        workspace_root: The workspace root path.

    Returns:
        A workspace-scoped namespace string.
    """
    workspace_name = get_workspace_name(workspace_root)
    # Sanitize workspace name for namespace use
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in workspace_name)
    return f"{base_namespace}:{safe_name}"


def get_persistent_session_id(workspace_root: str, conversation_id: str | None = None) -> str:
    """Generate a persistent session ID for a workspace.

    The session ID is stable for a given workspace + conversation combination.
    This allows tracking all turns within an Augment conversation.

    Args:
        workspace_root: The workspace root path.
        conversation_id: The Augment conversation ID (if available).

    Returns:
        A stable session ID string.
    """
    workspace_id = get_workspace_id(workspace_root)
    workspace_name = get_workspace_name(workspace_root)

    if conversation_id:
        # Use conversation ID for turn-by-turn tracking within a conversation
        return f"augment:{workspace_name}:{conversation_id}"
    else:
        # Fall back to workspace-only session (shared across conversations)
        return f"augment:{workspace_name}:{workspace_id}"


def get_workspace_summary_view_name(workspace_root: str) -> str:
    """Get the summary view name for a workspace.

    This view summarizes all memories across all sessions for the workspace.

    Args:
        workspace_root: The workspace root path.

    Returns:
        Summary view name for the workspace.
    """
    workspace_name = get_workspace_name(workspace_root)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in workspace_name)
    return f"augment_workspace_{safe_name}"


def get_session_summary_view_name(workspace_root: str, session_id: str) -> str:
    """Get the summary view name for a specific session.

    This view summarizes memories for a specific session within a workspace.

    Args:
        workspace_root: The workspace root path.
        session_id: The session ID.

    Returns:
        Summary view name for the session.
    """
    workspace_name = get_workspace_name(workspace_root)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in workspace_name)
    # Hash the session ID for brevity
    session_hash = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    return f"augment_session_{safe_name}_{session_hash}"

