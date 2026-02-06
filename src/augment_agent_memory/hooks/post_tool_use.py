"""PostToolUse hook - captures tool usage patterns as memories (default off)."""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone

from agent_memory_client import MemoryAPIClient, MemoryClientConfig
from agent_memory_client.models import MemoryMessage

from ..config import load_config
from ..workspace import (
    get_persistent_session_id,
    get_workspace_namespace,
    get_workspace_root,
)


def format_tool_usage(hook_input: dict) -> str | None:
    """Format tool usage into a memory-worthy string."""
    tool_name = hook_input.get("tool_name", "unknown")
    tool_input = hook_input.get("tool_input", {})
    tool_error = hook_input.get("tool_error", "")
    file_changes = hook_input.get("file_changes", [])

    # Skip tools that aren't interesting for memory
    skip_tools = {"view", "codebase-retrieval", "web-search", "web-fetch"}
    if tool_name in skip_tools:
        return None

    parts = [f"Used tool: {tool_name}"]

    # Add relevant input details based on tool type
    if tool_name == "launch-process":
        command = tool_input.get("command", "")
        if command:
            parts.append(f"Command: {command[:200]}")  # Truncate long commands
    elif tool_name in ("str-replace-editor", "save-file"):
        path = tool_input.get("path", "")
        if path:
            parts.append(f"File: {path}")
    elif tool_name == "github-api":
        path = tool_input.get("path", "")
        method = tool_input.get("method", "GET")
        if path:
            parts.append(f"GitHub: {method} {path}")

    # Add file changes summary
    if file_changes:
        changes = []
        for change in file_changes[:5]:  # Limit to 5 files
            if isinstance(change, dict):
                change_type = change.get("changeType", "edit")
                path = change.get("path", "unknown")
                changes.append(f"{change_type}: {path}")
        if changes:
            parts.append("Changes: " + ", ".join(changes))

    # Add error if present
    if tool_error:
        parts.append(f"Error: {tool_error[:100]}")

    return " | ".join(parts)


async def run_hook() -> None:
    """Async entry point for PostToolUse hook."""
    config = load_config()

    # Tool tracking is off by default
    if not config.track_tool_usage:
        print(json.dumps({}))
        return

    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({}))
        return

    # Format tool usage
    tool_memory = format_tool_usage(hook_input)
    if not tool_memory:
        print(json.dumps({}))
        return

    # Extract workspace and conversation info
    workspace_roots = hook_input.get("workspace_roots", [])
    conversation_id = hook_input.get("conversation_id")
    workspace_root = get_workspace_root(workspace_roots)

    # Determine namespace
    namespace = config.namespace
    if config.use_workspace_namespace and workspace_root:
        namespace = get_workspace_namespace(config.namespace, workspace_root)

    # Determine session ID
    if config.use_persistent_session and workspace_root:
        session_id = get_persistent_session_id(workspace_root, conversation_id)
    else:
        session_id = f"augment-tools-{uuid.uuid4().hex[:8]}"

    client_config = MemoryClientConfig(
        base_url=config.server_url,
        timeout=config.timeout / 1000,
        default_namespace=namespace,
    )

    async with MemoryAPIClient(client_config) as client:
        try:
            # Create a system message for tool usage
            messages = [
                MemoryMessage(
                    role="system",
                    content=tool_memory,
                    id=str(uuid.uuid4()),
                    created_at=datetime.now(timezone.utc),
                )
            ]

            # Append messages to existing session (creates session if needed)
            # This preserves existing messages instead of replacing them
            await client.append_messages_to_working_memory(
                session_id=session_id,
                messages=messages,
                namespace=namespace,
                user_id=config.user_id,
            )

            print(json.dumps({}))

        except Exception as e:
            sys.stderr.write(f"Tool tracking error: {e}\n")
            print(json.dumps({}))


def main():
    """Main entry point for PostToolUse hook."""
    asyncio.run(run_hook())


if __name__ == "__main__":
    main()

