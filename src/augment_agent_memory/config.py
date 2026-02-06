"""Configuration for Augment Agent Memory integration."""

import os
from dataclasses import dataclass, field
from typing import Literal

MemoryStrategy = Literal["discrete", "summary", "preferences", "custom"]
SummaryGroupByField = Literal["user_id", "namespace", "session_id"]


@dataclass
class MemoryConfig:
    """Configuration for the memory integration."""

    # Server connection
    server_url: str = "http://localhost:8000"
    api_key: str | None = None
    bearer_token: str | None = None
    timeout: int = 30000

    # Base namespace and user
    namespace: str = "augment"
    user_id: str | None = None

    # Auto-capture and recall
    auto_capture: bool = True
    auto_recall: bool = True

    # Recall settings
    min_score: float = 0.3
    recall_limit: int = 5

    # Extraction strategy
    extraction_strategy: MemoryStrategy = "discrete"
    custom_prompt: str | None = None

    # Summary views
    summary_view_name: str = "augment_user_summary"
    summary_time_window_days: int = 30
    summary_group_by: list[SummaryGroupByField] = field(default_factory=lambda: ["user_id"])

    # Workspace-based features (new)
    use_workspace_namespace: bool = True  # Auto-scope namespace by workspace
    use_persistent_session: bool = True  # Use workspace-based persistent session ID
    create_workspace_summary: bool = True  # Create/use workspace-level summary view
    create_session_summary: bool = True  # Create/use session-level summary view

    # Tool usage tracking (default off)
    track_tool_usage: bool = False  # Capture PreToolUse/PostToolUse as memories


def _parse_bool(value: str | None, default: bool) -> bool:
    """Parse a boolean from environment variable."""
    if value is None:
        return default
    return value.lower() == "true"


def load_config() -> MemoryConfig:
    """Load configuration from environment variables."""
    config = MemoryConfig(
        # Server connection
        server_url=os.getenv("AGENT_MEMORY_SERVER_URL", "http://localhost:8000"),
        api_key=os.getenv("AGENT_MEMORY_API_KEY"),
        bearer_token=os.getenv("AGENT_MEMORY_BEARER_TOKEN"),
        timeout=int(os.getenv("AGENT_MEMORY_TIMEOUT", "30000")),
        # Base namespace and user
        namespace=os.getenv("AGENT_MEMORY_NAMESPACE", "augment"),
        user_id=os.getenv("AGENT_MEMORY_USER_ID"),
        # Auto-capture and recall
        auto_capture=_parse_bool(os.getenv("AGENT_MEMORY_AUTO_CAPTURE"), True),
        auto_recall=_parse_bool(os.getenv("AGENT_MEMORY_AUTO_RECALL"), True),
        # Recall settings
        min_score=float(os.getenv("AGENT_MEMORY_MIN_SCORE", "0.3")),
        recall_limit=int(os.getenv("AGENT_MEMORY_RECALL_LIMIT", "5")),
        # Extraction strategy
        extraction_strategy=os.getenv("AGENT_MEMORY_EXTRACTION_STRATEGY", "discrete"),  # type: ignore
        custom_prompt=os.getenv("AGENT_MEMORY_CUSTOM_PROMPT"),
        # Summary views
        summary_view_name=os.getenv("AGENT_MEMORY_SUMMARY_VIEW_NAME", "augment_user_summary"),
        summary_time_window_days=int(os.getenv("AGENT_MEMORY_SUMMARY_TIME_WINDOW_DAYS", "30")),
        # Workspace-based features
        use_workspace_namespace=_parse_bool(
            os.getenv("AGENT_MEMORY_USE_WORKSPACE_NAMESPACE"), True
        ),
        use_persistent_session=_parse_bool(
            os.getenv("AGENT_MEMORY_USE_PERSISTENT_SESSION"), True
        ),
        create_workspace_summary=_parse_bool(
            os.getenv("AGENT_MEMORY_CREATE_WORKSPACE_SUMMARY"), True
        ),
        create_session_summary=_parse_bool(
            os.getenv("AGENT_MEMORY_CREATE_SESSION_SUMMARY"), True
        ),
        # Tool usage tracking
        track_tool_usage=_parse_bool(os.getenv("AGENT_MEMORY_TRACK_TOOL_USAGE"), False),
    )

    # Parse summary_group_by from comma-separated string
    group_by_str = os.getenv("AGENT_MEMORY_SUMMARY_GROUP_BY", "user_id")
    valid_fields = {"user_id", "namespace", "session_id"}
    config.summary_group_by = [
        f for f in group_by_str.split(",") if f.strip() in valid_fields  # type: ignore
    ]

    return config

