"""Stop hook - captures conversation data and stores in memory (turn-by-turn)."""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone

from agent_memory_client import MemoryAPIClient, MemoryClientConfig
from agent_memory_client.models import (
    CreateSummaryViewRequest,
    MemoryMessage,
    MemoryStrategyConfig,
    WorkingMemory,
)

from ..config import load_config
from ..workspace import (
    get_persistent_session_id,
    get_session_summary_view_name,
    get_workspace_namespace,
    get_workspace_root,
    get_workspace_summary_view_name,
)


async def ensure_summary_view_exists(
    client: MemoryAPIClient,
    view_name: str,
    group_by: list[str],
) -> str | None:
    """Ensure a summary view exists, creating it if needed.

    Returns the view ID if found or created, None on error.
    """
    try:
        # List all views and find by name
        views = await client.list_summary_views()
        for view in views:
            if view.name == view_name:
                sys.stderr.write(f"Summary view exists: {view_name} (id={view.id})\n")
                return view.id

        # Not found, create it
        sys.stderr.write(f"Creating summary view: {view_name}\n")
        request = CreateSummaryViewRequest(
            name=view_name,
            source="long_term",
            group_by=group_by,
        )
        created = await client.create_summary_view(request)
        return created.id
    except Exception as e:
        sys.stderr.write(f"Error with summary view {view_name}: {e}\n")
        return None


def extract_messages_from_conversation(conversation: dict) -> list[MemoryMessage]:
    """Extract messages from Augment conversation data."""
    messages = []
    now = datetime.now(timezone.utc)

    # Extract user prompt
    user_prompt = conversation.get("userPrompt")
    if user_prompt:
        messages.append(
            MemoryMessage(
                role="user",
                content=user_prompt,
                id=str(uuid.uuid4()),
                created_at=now,
            )
        )

    # Extract agent response (prefer text, fall back to code)
    agent_text = conversation.get("agentTextResponse")
    agent_code = conversation.get("agentCodeResponse")

    # Build agent response - combine text and code if both present
    response_parts = []
    if agent_text:
        response_parts.append(agent_text)
    if agent_code:
        # Format code changes if it's a list
        if isinstance(agent_code, list):
            for change in agent_code:
                if isinstance(change, dict):
                    path = change.get("path", "unknown")
                    change_type = change.get("changeType", "edit")
                    response_parts.append(f"[{change_type}: {path}]")
        else:
            response_parts.append(str(agent_code))

    if response_parts:
        messages.append(
            MemoryMessage(
                role="assistant",
                content="\n\n".join(response_parts),
                id=str(uuid.uuid4()),
                created_at=now,
            )
        )

    return messages


async def run_hook() -> None:
    """Async entry point for Stop hook - saves conversation turn immediately."""
    config = load_config()

    if not config.auto_capture:
        print(json.dumps({}))
        return

    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({}))
        return

    # Extract conversation data (requires includeConversationData: true in hook config)
    conversation = hook_input.get("conversation", {})
    if not conversation:
        print(json.dumps({}))
        return

    # Extract workspace and conversation info
    workspace_roots = hook_input.get("workspace_roots", [])
    conversation_id = hook_input.get("conversation_id")
    workspace_root = get_workspace_root(workspace_roots)

    # Determine namespace (workspace-scoped if enabled)
    namespace = config.namespace
    if config.use_workspace_namespace and workspace_root:
        namespace = get_workspace_namespace(config.namespace, workspace_root)

    # Determine session ID (persistent for turn-by-turn tracking)
    if config.use_persistent_session and workspace_root:
        session_id = get_persistent_session_id(workspace_root, conversation_id)
    else:
        # Fall back to timestamp-based session ID
        session_id = (
            f"augment-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            f"-{uuid.uuid4().hex[:8]}"
        )

    client_config = MemoryClientConfig(
        base_url=config.server_url,
        timeout=config.timeout / 1000,
        default_namespace=namespace,
    )

    async with MemoryAPIClient(client_config) as client:
        try:
            # Convert conversation to messages
            messages = extract_messages_from_conversation(conversation)

            if not messages:
                print(json.dumps({}))
                return

            # Configure extraction strategy
            strategy_config = MemoryStrategyConfig(
                strategy=config.extraction_strategy,
            )

            # Create working memory with messages for this turn
            # Using persistent session ID means all turns in the same conversation
            # get added to the same working memory, building the thread
            working_memory = WorkingMemory(
                session_id=session_id,
                namespace=namespace,
                user_id=config.user_id,
                messages=messages,
                long_term_memory_strategy=strategy_config,
            )

            # Store in working memory - this adds to existing messages for the session
            # Background extraction will process and create long-term memories
            await client.put_working_memory(
                session_id=session_id,
                memory=working_memory,
            )
            sys.stderr.write(f"Saved {len(messages)} messages to working memory\n")

            # Kick off async refresh of summary views (ensure they exist first)
            if config.create_workspace_summary and workspace_root:
                ws_view_name = get_workspace_summary_view_name(workspace_root)
                ws_view_id = await ensure_summary_view_exists(client, ws_view_name, ["namespace"])
                if ws_view_id:
                    try:
                        task = await client.run_summary_view(ws_view_id)
                        sys.stderr.write(f"Started workspace summary refresh task: {task.id}\n")
                    except Exception as e:
                        sys.stderr.write(f"Failed to start workspace summary refresh: {e}\n")

            if config.create_session_summary and workspace_root:
                sess_view_name = get_session_summary_view_name(workspace_root, session_id)
                sess_view_id = await ensure_summary_view_exists(client, sess_view_name, ["namespace", "session_id"])
                if sess_view_id:
                    try:
                        task = await client.run_summary_view(sess_view_id)
                        sys.stderr.write(f"Started session summary refresh task: {task.id}\n")
                    except Exception as e:
                        sys.stderr.write(f"Failed to start session summary refresh: {e}\n")

            print(json.dumps({}))

        except Exception as e:
            sys.stderr.write(f"Memory capture error: {e}\n")
            print(json.dumps({}))


def main():
    """Main entry point for Stop hook."""
    asyncio.run(run_hook())


if __name__ == "__main__":
    main()

