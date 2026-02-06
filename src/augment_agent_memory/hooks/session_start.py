"""SessionStart hook - injects memory context at session start."""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

from agent_memory_client import MemoryAPIClient, MemoryClientConfig
from agent_memory_client.filters import CreatedAt, Namespace, UserId
from agent_memory_client.models import CreateSummaryViewRequest

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
) -> None:
    """Ensure a summary view exists, creating it if needed."""
    try:
        existing = await client.get_summary_view(view_name)
        if existing is None:
            sys.stderr.write(f"Creating summary view: {view_name}\n")
            # Create the summary view
            request = CreateSummaryViewRequest(
                name=view_name,
                source="long_term",
                group_by=group_by,
            )
            await client.create_summary_view(request)
        else:
            sys.stderr.write(f"Summary view exists: {view_name}\n")
    except Exception as e:
        # Don't fail if we can't create the view
        sys.stderr.write(f"Error with summary view {view_name}: {e}\n")


async def get_summary_context(
    client: MemoryAPIClient,
    view_name: str,
    group: dict[str, str],
) -> str | None:
    """Get summary from a summary view by running the partition.

    Args:
        client: Memory API client
        view_name: Name of the summary view
        group: Concrete values for the view's group_by fields
            e.g., {"namespace": "my-namespace"} or {"namespace": "ns", "session_id": "sess"}
    """
    try:
        sys.stderr.write(f"Running partition for {view_name} with group={group}\n")
        result = await client.run_summary_view_partition(view_name, group)
        if result and result.summary:
            sys.stderr.write(f"Got summary from {view_name}: {len(result.summary)} chars, {result.memory_count} memories\n")
            return result.summary
        else:
            sys.stderr.write(f"No summary generated for {view_name}\n")
    except Exception as e:
        sys.stderr.write(f"Error getting summary from {view_name}: {e}\n")
    return None


async def search_relevant_memories(
    client: MemoryAPIClient,
    query: str,
    namespace: str | None = None,
    user_id: str | None = None,
    limit: int = 5,
    min_score: float = 0.3,
    time_window_days: int = 30,
) -> list[str]:
    """Search for memories relevant to the query."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=time_window_days)
        results = await client.search_long_term_memory(
            text=query,
            namespace=Namespace(eq=namespace) if namespace else None,
            user_id=UserId(eq=user_id) if user_id else None,
            created_at=CreatedAt(gte=cutoff),
            limit=limit,
            distance_threshold=1 - min_score,
        )
        memories = [m.text for m in results.memories if m.text]
        sys.stderr.write(f"Found {len(memories)} relevant memories\n")
        return memories
    except Exception as e:
        sys.stderr.write(f"Error searching memories: {e}\n")
        return []


def build_context(
    workspace_summary: str | None,
    session_summary: str | None,
    memories: list[str],
) -> str:
    """Build the context string to inject into the session."""
    parts = []

    if workspace_summary:
        parts.append(f"## Workspace Context\n{workspace_summary}")

    if session_summary:
        parts.append(f"## Session Context\n{session_summary}")

    if memories:
        parts.append("## Relevant Memories")
        for i, mem in enumerate(memories, 1):
            parts.append(f"{i}. {mem}")

    return "\n\n".join(parts) if parts else ""


async def run_hook() -> None:
    """Async entry point for SessionStart hook."""
    config = load_config()

    if not config.auto_recall:
        print(json.dumps({}))
        return

    # Read hook input from stdin
    hook_input = {}
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        pass

    # Extract workspace and conversation info from hook input
    workspace_roots = hook_input.get("workspace_roots", [])
    conversation_id = hook_input.get("conversation_id")
    workspace_root = get_workspace_root(workspace_roots)

    # Determine namespace (workspace-scoped if enabled)
    namespace = config.namespace
    if config.use_workspace_namespace and workspace_root:
        namespace = get_workspace_namespace(config.namespace, workspace_root)

    # Determine session ID (persistent if enabled)
    session_id = None
    if config.use_persistent_session and workspace_root:
        session_id = get_persistent_session_id(workspace_root, conversation_id)

    sys.stderr.write(f"SessionStart: namespace={namespace}, session_id={session_id}, workspace={workspace_root}\n")

    client_config = MemoryClientConfig(
        base_url=config.server_url,
        timeout=config.timeout / 1000,
        default_namespace=namespace,
    )

    async with MemoryAPIClient(client_config) as client:
        try:
            workspace_summary = None
            session_summary = None

            # Get workspace-level summary if enabled
            if config.create_workspace_summary and workspace_root and namespace:
                ws_view_name = get_workspace_summary_view_name(workspace_root)
                await ensure_summary_view_exists(client, ws_view_name, ["namespace"])
                workspace_summary = await get_summary_context(
                    client, ws_view_name, group={"namespace": namespace}
                )

            # Get session-level summary if enabled
            if config.create_session_summary and workspace_root and session_id and namespace:
                sess_view_name = get_session_summary_view_name(workspace_root, session_id)
                await ensure_summary_view_exists(
                    client, sess_view_name, ["namespace", "session_id"]
                )
                session_summary = await get_summary_context(
                    client, sess_view_name, group={"namespace": namespace, "session_id": session_id}
                )

            # Search for relevant memories using generic query
            # (query-based recall uses actual user prompt when available)
            query = "recent conversation context and user preferences"
            memories = await search_relevant_memories(
                client,
                query=query,
                namespace=namespace,
                user_id=config.user_id,
                limit=config.recall_limit,
                min_score=config.min_score,
                time_window_days=config.summary_time_window_days,
            )

            # Build and output context
            context = build_context(workspace_summary, session_summary, memories)

            if context:
                print(context)
            else:
                print(json.dumps({}))

        except Exception as e:
            sys.stderr.write(f"Memory recall error: {e}\n")
            print(json.dumps({}))


def main():
    """Main entry point for SessionStart hook."""
    asyncio.run(run_hook())


if __name__ == "__main__":
    main()

