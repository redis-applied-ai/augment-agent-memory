# Augment Agent Memory

Redis Agent Memory integration for Augment Code CLI (Augie). Provides persistent memory across sessions using the [Redis Agent Memory Server](https://redis.github.io/agent-memory-server).

## Features

- **Automatic memory recall** - Injects relevant context at session start
- **Turn-by-turn capture** - Saves each conversation turn immediately
- **Workspace-scoped memories** - Memories are organized by project/workspace
- **Dual summary views** - Workspace-level and session-level summaries
- **Tool usage tracking** - Optional capture of tool usage patterns

## Prerequisites

- Python 3.10+
- A running [Redis Agent Memory Server](https://redis.github.io/agent-memory-server)
- [Augment Code CLI](https://docs.augmentcode.com/cli) installed

### Starting the Memory Server

If you don't already have a Redis Agent Memory Server running, you can start the standalone Docker image:

```bash
docker run -d \
  --name agent-memory \
  --platform linux/amd64 \
  --env-file .env \
  -p 8000:8000 \
  -p 6899:6379 \
  redislabs/agent-memory-server:0.13.1-standalone
```

This starts the memory server on port 8000 with an embedded Redis instance on port 6899.

Create a `.env` file with your configuration:

```bash
# .env
OPENAI_API_KEY=your-openai-key  # Required for embeddings
```

Verify the server is running:

```bash
curl http://localhost:8000/health
```

## Installation

```bash
# Install from source
pip install -e .

# Or with uv
uv pip install -e .
```

## Quick Start

### 1. Configure Environment Variables

Add these to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
# Required
export AGENT_MEMORY_SERVER_URL=http://localhost:8000
export AGENT_MEMORY_NAMESPACE=augment
export AGENT_MEMORY_USER_ID=your-user-id

# Optional (with defaults shown)
export AGENT_MEMORY_API_KEY=           # API key if server requires auth
export AGENT_MEMORY_AUTO_RECALL=true   # Inject memories at session start
export AGENT_MEMORY_AUTO_CAPTURE=true  # Save conversations automatically
```

### 2. Install Hooks

Run the installer to set up Augment hooks:

```bash
augment-memory-install
```

This creates shell script wrappers and configures `~/.augment/settings.json`.

### 3. Verify Installation

Check that the hooks are configured:

```bash
cat ~/.augment/settings.json
```

You should see hook entries for `SessionStart` and `Stop`.

## How It Works

Augment hooks must be shell scripts. This package creates shell script wrappers in `~/.augment/memory-hooks/` that invoke the Python handlers:

```
~/.augment/memory-hooks/
├── session_start.sh    # Injects memory context
├── stop.sh             # Captures conversation turns
└── post_tool_use.sh    # Tracks tool usage (optional)
```

Each shell script simply calls the corresponding Python module:

```bash
#!/bin/bash
exec /path/to/python -m augment_agent_memory.hooks.session_start
```

The hooks receive JSON input via stdin and output context via stdout.

### Hook Flow

1. **SessionStart** - When you start a conversation:
   - Searches for relevant memories from the workspace
   - Retrieves workspace and session summaries
   - Outputs context that Augment injects into the conversation

2. **Stop** - After each turn:
   - Captures the user prompt and agent response
   - Stores in working memory with persistent session ID
   - Background extraction creates long-term memories

3. **PostToolUse** (optional) - After tool execution:
   - Records which tools were used and how
   - Useful for tracking patterns and debugging

## Configuration Reference

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MEMORY_SERVER_URL` | `http://localhost:8000` | Memory server URL |
| `AGENT_MEMORY_API_KEY` | - | API key for authentication |
| `AGENT_MEMORY_NAMESPACE` | `augment` | Base namespace for memories |
| `AGENT_MEMORY_USER_ID` | - | User ID for memory isolation |

### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MEMORY_AUTO_RECALL` | `true` | Inject memories at session start |
| `AGENT_MEMORY_AUTO_CAPTURE` | `true` | Save conversations automatically |
| `AGENT_MEMORY_USE_WORKSPACE_NAMESPACE` | `true` | Scope memories by workspace |
| `AGENT_MEMORY_USE_PERSISTENT_SESSION` | `true` | Use stable session IDs for threading |
| `AGENT_MEMORY_CREATE_WORKSPACE_SUMMARY` | `true` | Create workspace-level summaries |
| `AGENT_MEMORY_CREATE_SESSION_SUMMARY` | `true` | Create session-level summaries |
| `AGENT_MEMORY_TRACK_TOOL_USAGE` | `false` | Track tool usage as memories |

### Recall Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_MEMORY_MIN_SCORE` | `0.3` | Minimum similarity score for recall |
| `AGENT_MEMORY_RECALL_LIMIT` | `5` | Max memories to retrieve |
| `AGENT_MEMORY_SUMMARY_TIME_WINDOW_DAYS` | `30` | Time window for memory search |

## Manual Installation

If you prefer to configure hooks manually:

### 1. Create Hook Scripts

Create `~/.augment/memory-hooks/session_start.sh`:

```bash
#!/bin/bash
exec /path/to/your/python -m augment_agent_memory.hooks.session_start
```

Create `~/.augment/memory-hooks/stop.sh`:

```bash
#!/bin/bash
exec /path/to/your/python -m augment_agent_memory.hooks.stop
```

Make them executable:

```bash
chmod +x ~/.augment/memory-hooks/*.sh
```

### 2. Configure settings.json

Edit `~/.augment/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/you/.augment/memory-hooks/session_start.sh",
            "timeout": 10000
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/you/.augment/memory-hooks/stop.sh",
            "timeout": 10000
          }
        ],
        "metadata": {
          "includeConversationData": true
        }
      }
    ]
  }
}
```

## Enabling Tool Tracking

To track tool usage (disabled by default):

```bash
# Via installer
augment-memory-install --enable-tool-tracking

# Or via environment variable
export AGENT_MEMORY_TRACK_TOOL_USAGE=true
```

## Troubleshooting

### Hooks not running

1. Check that scripts are executable: `ls -la ~/.augment/memory-hooks/`
2. Verify settings.json syntax: `cat ~/.augment/settings.json | jq .`
3. Test hooks manually: `echo '{}' | ~/.augment/memory-hooks/session_start.sh`

### Memory server connection errors

1. Verify server is running: `curl http://localhost:8000/health`
2. Check environment variables are set: `env | grep AGENT_MEMORY`

### No memories being recalled

1. Check that memories exist in the server
2. Verify namespace and user_id match
3. Try lowering `AGENT_MEMORY_MIN_SCORE`

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest -v

# Run linting
ruff check .
```

