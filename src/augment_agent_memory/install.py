"""Installation helper for Augment memory hooks."""

import json
import stat
import sys
from pathlib import Path


def get_augment_settings_path() -> Path:
    """Get the Augment settings.json path."""
    home = Path.home()
    return home / ".augment" / "settings.json"


def get_hooks_dir() -> Path:
    """Get the directory for hook scripts."""
    home = Path.home()
    hooks_dir = home / ".augment" / "memory-hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    return hooks_dir


def create_hook_scripts(hooks_dir: Path, use_fixed_python: bool = True) -> dict[str, Path]:
    """Create shell script wrappers for the Python hooks.

    Args:
        hooks_dir: Directory to create scripts in.
        use_fixed_python: If True, use the current Python executable path.
            If False, use the 'augment-memory-*' entry points which rely on PATH.
    """
    scripts = {}

    if use_fixed_python:
        # Use the specific Python that has the package installed
        python_exe = sys.executable
        session_start_cmd = f"{python_exe} -m augment_agent_memory.hooks.session_start"
        stop_cmd = f"{python_exe} -m augment_agent_memory.hooks.stop"
        post_tool_cmd = f"{python_exe} -m augment_agent_memory.hooks.post_tool_use"
    else:
        # Use entry points - requires package to be installed in PATH's Python
        session_start_cmd = "augment-memory-session-start"
        stop_cmd = "augment-memory-stop"
        post_tool_cmd = "augment-memory-post-tool-use"

    # SessionStart hook script
    session_start_script = hooks_dir / "session_start.sh"
    session_start_script.write_text(f"""#!/bin/bash
# Augment Memory - SessionStart Hook
exec {session_start_cmd}
""")
    session_start_script.chmod(session_start_script.stat().st_mode | stat.S_IEXEC)
    scripts["SessionStart"] = session_start_script

    # Stop hook script
    stop_script = hooks_dir / "stop.sh"
    stop_script.write_text(f"""#!/bin/bash
# Augment Memory - Stop Hook
exec {stop_cmd}
""")
    stop_script.chmod(stop_script.stat().st_mode | stat.S_IEXEC)
    scripts["Stop"] = stop_script

    # PostToolUse hook script (for tool tracking, disabled by default)
    post_tool_script = hooks_dir / "post_tool_use.sh"
    post_tool_script.write_text(f"""#!/bin/bash
# Augment Memory - PostToolUse Hook (tool tracking)
exec {post_tool_cmd}
""")
    post_tool_script.chmod(post_tool_script.stat().st_mode | stat.S_IEXEC)
    scripts["PostToolUse"] = post_tool_script

    return scripts


def update_augment_settings(
    scripts: dict[str, Path], enable_tool_tracking: bool = False
) -> None:
    """Update Augment settings.json with hook configuration.

    Uses the new Augment hooks format with nested hooks arrays.
    """
    settings_path = get_augment_settings_path()

    # Load existing settings or create new
    if settings_path.exists():
        with open(settings_path) as f:
            settings = json.load(f)
    else:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {}

    # Ensure hooks section exists
    if "hooks" not in settings:
        settings["hooks"] = {}

    # Helper to add hook if not present
    def add_hook(event_name: str, hook_config: dict) -> None:
        if event_name not in settings["hooks"]:
            settings["hooks"][event_name] = []

        # Check if our hook is already configured
        script_path = str(scripts.get(event_name, ""))
        for existing in settings["hooks"][event_name]:
            # Check both old format (path) and new format (hooks[].command)
            if existing.get("path") == script_path:
                return
            hooks_list = existing.get("hooks", [])
            for h in hooks_list:
                if h.get("command") == script_path:
                    return

        settings["hooks"][event_name].append(hook_config)

    # SessionStart hook - injects memory context
    add_hook(
        "SessionStart",
        {
            "hooks": [
                {
                    "type": "command",
                    "command": str(scripts["SessionStart"]),
                    "timeout": 10000,
                }
            ],
        },
    )

    # Stop hook - captures conversation data (turn-by-turn)
    add_hook(
        "Stop",
        {
            "hooks": [
                {
                    "type": "command",
                    "command": str(scripts["Stop"]),
                    "timeout": 10000,
                }
            ],
            "metadata": {
                "includeConversationData": True,
            },
        },
    )

    # PostToolUse hook - tool tracking (off by default, controlled by env var)
    if enable_tool_tracking:
        add_hook(
            "PostToolUse",
            {
                "matcher": ".*",  # Match all tools
                "hooks": [
                    {
                        "type": "command",
                        "command": str(scripts["PostToolUse"]),
                        "timeout": 5000,
                    }
                ],
            },
        )

    # Write updated settings
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)

    print(f"Updated Augment settings: {settings_path}")


def main():
    """Install Augment memory hooks."""
    import argparse

    parser = argparse.ArgumentParser(description="Install Augment Agent Memory hooks")
    parser.add_argument(
        "--enable-tool-tracking",
        action="store_true",
        help="Enable PostToolUse hook for tool usage tracking",
    )
    parser.add_argument(
        "--use-path",
        action="store_true",
        help="Use entry point commands (augment-memory-*) instead of fixed Python path. "
        "Requires the package to be installed in a Python that's in your PATH.",
    )
    args = parser.parse_args()

    print("Installing Augment Agent Memory hooks...")

    # Create hook scripts
    hooks_dir = get_hooks_dir()
    scripts = create_hook_scripts(hooks_dir, use_fixed_python=not args.use_path)
    print(f"Created hook scripts in: {hooks_dir}")

    if args.use_path:
        print("Using PATH-based entry points (augment-memory-* commands)")
    else:
        print(f"Using Python: {sys.executable}")

    # Update Augment settings
    update_augment_settings(scripts, enable_tool_tracking=args.enable_tool_tracking)

    print("\nInstallation complete!")
    print("\nConfigure the memory server:")
    print("  export AGENT_MEMORY_SERVER_URL=http://localhost:8000")
    print("  export AGENT_MEMORY_NAMESPACE=augment")
    print("  export AGENT_MEMORY_USER_ID=your-user-id")
    print("\nOptional settings:")
    print("  export AGENT_MEMORY_USE_WORKSPACE_NAMESPACE=true  # Scope by workspace")
    print("  export AGENT_MEMORY_USE_PERSISTENT_SESSION=true   # Turn-by-turn threading")
    print("  export AGENT_MEMORY_TRACK_TOOL_USAGE=false        # Tool usage tracking")


if __name__ == "__main__":
    main()

