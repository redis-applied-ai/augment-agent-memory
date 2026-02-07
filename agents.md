# Augment Agent Memory - Agent Guidelines

## Project Overview

This is an Augment Code CLI plugin that provides persistent memory across sessions using Redis Agent Memory Server. It installs hooks into `~/.augment/settings.json` that capture conversations and recall relevant context.

## Key Architecture

### Hook System
- **SessionStart hook**: Recalls memories and injects context at conversation start
- **Stop hook**: Captures each conversation turn immediately after it completes
- **PostToolUse hook**: Optional tool usage tracking (disabled by default)

Hooks are shell scripts in `~/.augment/memory-hooks/` that invoke Python modules.

### Installation Behavior
The installer (`src/augment_agent_memory/install.py`) is **additive**:
- Does not overwrite existing hooks in settings.json
- Only adds this plugin's hooks if not already present
- Safe to run multiple times or alongside other plugins

### Workspace Scoping
Memories are scoped by workspace using a hash of the workspace path. This keeps project-specific context separate.

## File Structure

```
src/augment_agent_memory/
├── __init__.py
├── config.py          # Environment variable configuration
├── install.py         # Hook installer (augment-memory-install)
├── workspace.py       # Workspace/session ID utilities
└── hooks/
    ├── __init__.py
    ├── session_start.py   # Memory recall hook
    ├── stop.py            # Conversation capture hook
    └── post_tool_use.py   # Tool tracking hook
```

## Development Commands

```bash
# Install in development mode
uv pip install -e .

# Run tests
pytest -v

# Run linting
ruff check .

# Install hooks locally
augment-memory-install
```

## Testing

Tests use testcontainers for Redis. Key test files:
- `tests/test_config.py` - Configuration loading
- `tests/test_hooks.py` - Hook behavior
- `tests/test_workspace.py` - Workspace utilities

## Environment Variables

Core settings are loaded from environment in `config.py`:
- `AGENT_MEMORY_SERVER_URL` - Memory server endpoint
- `AGENT_MEMORY_NAMESPACE` - Base namespace
- `AGENT_MEMORY_USER_ID` - User identifier

See README.md for full configuration reference.

## Common Tasks

### Adding a New Hook
1. Create handler in `src/augment_agent_memory/hooks/`
2. Add shell script creation in `install.py:create_hook_scripts()`
3. Add settings update in `install.py:update_augment_settings()`
4. Add entry point in `pyproject.toml`

### Modifying Memory Capture
The Stop hook (`hooks/stop.py`) handles conversation capture. It:
1. Reads conversation data from stdin
2. Creates MemoryMessage objects
3. Sends to memory server via client

### Modifying Memory Recall
The SessionStart hook (`hooks/session_start.py`) handles recall. It:
1. Searches for relevant memories
2. Retrieves summary views
3. Outputs context to stdout for injection

