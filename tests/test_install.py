"""Tests for the install module."""

import json
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

from augment_agent_memory.install import (
    create_hook_scripts,
    get_augment_settings_path,
    get_hooks_dir,
    get_log_file,
    update_augment_settings,
)


class TestGetPaths:
    """Tests for path helper functions."""

    def test_get_augment_settings_path(self):
        """Test that settings path is in home directory."""
        path = get_augment_settings_path()
        assert path.name == "settings.json"
        assert ".augment" in str(path)

    def test_get_hooks_dir(self):
        """Test that hooks dir is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("augment_agent_memory.install.Path.home", return_value=Path(tmpdir)):
                hooks_dir = get_hooks_dir()
                assert hooks_dir.exists()
                assert hooks_dir.name == "memory-hooks"

    def test_get_log_file(self):
        """Test that log file path is correct."""
        path = get_log_file()
        assert path.name == "hooks.log"
        assert "memory-hooks" in str(path)


class TestCreateHookScripts:
    """Tests for create_hook_scripts function."""

    def test_creates_all_scripts(self):
        """Test that all hook scripts are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir)
            scripts = create_hook_scripts(hooks_dir)

            assert "SessionStart" in scripts
            assert "Stop" in scripts
            assert "PostToolUse" in scripts

    def test_scripts_are_executable(self):
        """Test that created scripts are executable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir)
            scripts = create_hook_scripts(hooks_dir)

            for script_path in scripts.values():
                assert script_path.exists()
                mode = script_path.stat().st_mode
                assert mode & stat.S_IEXEC

    def test_scripts_contain_python_command(self):
        """Test that scripts contain Python module invocation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir)
            scripts = create_hook_scripts(hooks_dir, use_fixed_python=True)

            session_start_content = scripts["SessionStart"].read_text()
            assert "augment_agent_memory.hooks.session_start" in session_start_content

    def test_scripts_use_entry_points_when_not_fixed(self):
        """Test that scripts use entry points when use_fixed_python=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir)
            scripts = create_hook_scripts(hooks_dir, use_fixed_python=False)

            session_start_content = scripts["SessionStart"].read_text()
            assert "augment-memory-session-start" in session_start_content


class TestUpdateAugmentSettings:
    """Tests for update_augment_settings function."""

    def test_creates_new_settings_file(self):
        """Test that settings file is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / ".augment" / "settings.json"
            scripts = {
                "SessionStart": Path("/path/to/session_start.sh"),
                "Stop": Path("/path/to/stop.sh"),
                "PostToolUse": Path("/path/to/post_tool_use.sh"),
            }

            with patch(
                "augment_agent_memory.install.get_augment_settings_path",
                return_value=settings_path,
            ):
                update_augment_settings(scripts)

            assert settings_path.exists()
            settings = json.loads(settings_path.read_text())
            assert "hooks" in settings
            assert "SessionStart" in settings["hooks"]
            assert "Stop" in settings["hooks"]

    def test_preserves_existing_hooks(self):
        """Test that existing hooks are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / ".augment" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            existing_settings = {
                "hooks": {
                    "SessionStart": [{"hooks": [{"command": "/other/hook.sh"}]}],
                },
                "other_setting": "value",
            }
            settings_path.write_text(json.dumps(existing_settings))

            scripts = {
                "SessionStart": Path("/path/to/session_start.sh"),
                "Stop": Path("/path/to/stop.sh"),
                "PostToolUse": Path("/path/to/post_tool_use.sh"),
            }

            with patch(
                "augment_agent_memory.install.get_augment_settings_path",
                return_value=settings_path,
            ):
                update_augment_settings(scripts)

            settings = json.loads(settings_path.read_text())
            # Should have both hooks
            assert len(settings["hooks"]["SessionStart"]) == 2
            # Other settings preserved
            assert settings["other_setting"] == "value"

    def test_does_not_duplicate_hooks(self):
        """Test that hooks are not duplicated on re-run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / ".augment" / "settings.json"
            settings_path.parent.mkdir(parents=True)

            scripts = {
                "SessionStart": Path("/path/to/session_start.sh"),
                "Stop": Path("/path/to/stop.sh"),
                "PostToolUse": Path("/path/to/post_tool_use.sh"),
            }

            with patch(
                "augment_agent_memory.install.get_augment_settings_path",
                return_value=settings_path,
            ):
                # Run twice
                update_augment_settings(scripts)
                update_augment_settings(scripts)

            settings = json.loads(settings_path.read_text())
            # Should still have only one hook each
            assert len(settings["hooks"]["SessionStart"]) == 1
            assert len(settings["hooks"]["Stop"]) == 1

    def test_adds_post_tool_use_when_enabled(self):
        """Test that PostToolUse hook is added when enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / ".augment" / "settings.json"
            settings_path.parent.mkdir(parents=True)

            scripts = {
                "SessionStart": Path("/path/to/session_start.sh"),
                "Stop": Path("/path/to/stop.sh"),
                "PostToolUse": Path("/path/to/post_tool_use.sh"),
            }

            with patch(
                "augment_agent_memory.install.get_augment_settings_path",
                return_value=settings_path,
            ):
                update_augment_settings(scripts, enable_tool_tracking=True)

            settings = json.loads(settings_path.read_text())
            assert "PostToolUse" in settings["hooks"]
            assert len(settings["hooks"]["PostToolUse"]) == 1

    def test_detects_old_format_path(self):
        """Test that old format hooks with 'path' key are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / ".augment" / "settings.json"
            settings_path.parent.mkdir(parents=True)
            existing_settings = {
                "hooks": {
                    "SessionStart": [{"path": "/path/to/session_start.sh"}],
                },
            }
            settings_path.write_text(json.dumps(existing_settings))

            scripts = {
                "SessionStart": Path("/path/to/session_start.sh"),
                "Stop": Path("/path/to/stop.sh"),
                "PostToolUse": Path("/path/to/post_tool_use.sh"),
            }

            with patch(
                "augment_agent_memory.install.get_augment_settings_path",
                return_value=settings_path,
            ):
                update_augment_settings(scripts)

            settings = json.loads(settings_path.read_text())
            # Should not duplicate - old format detected
            assert len(settings["hooks"]["SessionStart"]) == 1


class TestInstallMain:
    """Tests for the main install function."""

    def test_main_default_options(self):
        """Test main with default options."""
        from augment_agent_memory.install import main

        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir) / ".augment" / "memory-hooks"
            settings_path = Path(tmpdir) / ".augment" / "settings.json"

            with (
                patch("augment_agent_memory.install.get_hooks_dir", return_value=hooks_dir),
                patch(
                    "augment_agent_memory.install.get_augment_settings_path",
                    return_value=settings_path,
                ),
                patch("sys.argv", ["augment-memory-install"]),
                patch("builtins.print"),
            ):
                hooks_dir.mkdir(parents=True)
                main()

            assert settings_path.exists()

    def test_main_with_tool_tracking(self):
        """Test main with tool tracking enabled."""
        from augment_agent_memory.install import main

        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir) / ".augment" / "memory-hooks"
            settings_path = Path(tmpdir) / ".augment" / "settings.json"

            with (
                patch("augment_agent_memory.install.get_hooks_dir", return_value=hooks_dir),
                patch(
                    "augment_agent_memory.install.get_augment_settings_path",
                    return_value=settings_path,
                ),
                patch("sys.argv", ["augment-memory-install", "--enable-tool-tracking"]),
                patch("builtins.print"),
            ):
                hooks_dir.mkdir(parents=True)
                main()

            settings = json.loads(settings_path.read_text())
            assert "PostToolUse" in settings["hooks"]

    def test_main_with_use_path(self):
        """Test main with use-path option."""
        from augment_agent_memory.install import main

        with tempfile.TemporaryDirectory() as tmpdir:
            hooks_dir = Path(tmpdir) / ".augment" / "memory-hooks"
            settings_path = Path(tmpdir) / ".augment" / "settings.json"

            with (
                patch("augment_agent_memory.install.get_hooks_dir", return_value=hooks_dir),
                patch(
                    "augment_agent_memory.install.get_augment_settings_path",
                    return_value=settings_path,
                ),
                patch("sys.argv", ["augment-memory-install", "--use-path"]),
                patch("builtins.print"),
            ):
                hooks_dir.mkdir(parents=True)
                main()

            # Check that scripts use entry points
            session_start_script = hooks_dir / "session_start.sh"
            content = session_start_script.read_text()
            assert "augment-memory-session-start" in content

