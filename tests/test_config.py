"""Tests for configuration loading."""



from augment_agent_memory.config import MemoryConfig, load_config


class TestMemoryConfig:
    """Tests for MemoryConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = MemoryConfig()
        assert config.server_url == "http://localhost:8000"
        assert config.namespace == "augment"
        assert config.auto_capture is True
        assert config.auto_recall is True
        assert config.min_score == 0.3
        assert config.recall_limit == 5
        assert config.extraction_strategy == "discrete"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = MemoryConfig(
            server_url="http://custom:9000",
            namespace="custom_ns",
            user_id="test_user",
            auto_capture=False,
            recall_limit=10,
        )
        assert config.server_url == "http://custom:9000"
        assert config.namespace == "custom_ns"
        assert config.user_id == "test_user"
        assert config.auto_capture is False
        assert config.recall_limit == 10


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_from_env(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("AGENT_MEMORY_SERVER_URL", "http://test:8080")
        monkeypatch.setenv("AGENT_MEMORY_NAMESPACE", "test_namespace")
        monkeypatch.setenv("AGENT_MEMORY_USER_ID", "test_user")
        monkeypatch.setenv("AGENT_MEMORY_AUTO_CAPTURE", "false")
        monkeypatch.setenv("AGENT_MEMORY_MIN_SCORE", "0.5")
        monkeypatch.setenv("AGENT_MEMORY_RECALL_LIMIT", "10")

        config = load_config()

        assert config.server_url == "http://test:8080"
        assert config.namespace == "test_namespace"
        assert config.user_id == "test_user"
        assert config.auto_capture is False
        assert config.min_score == 0.5
        assert config.recall_limit == 10

    def test_load_defaults(self, monkeypatch):
        """Test loading with default values when env vars not set."""
        # Clear relevant env vars
        for key in [
            "AGENT_MEMORY_SERVER_URL",
            "AGENT_MEMORY_NAMESPACE",
            "AGENT_MEMORY_USER_ID",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = load_config()

        assert config.server_url == "http://localhost:8000"
        assert config.namespace == "augment"
        assert config.user_id is None

    def test_load_summary_group_by(self, monkeypatch):
        """Test loading summary_group_by from environment."""
        monkeypatch.setenv("AGENT_MEMORY_SUMMARY_GROUP_BY", "user_id,namespace")
        config = load_config()
        assert config.summary_group_by == ["user_id", "namespace"]

    def test_load_invalid_summary_group_by(self, monkeypatch):
        """Test that invalid group_by fields are filtered out."""
        monkeypatch.setenv("AGENT_MEMORY_SUMMARY_GROUP_BY", "user_id,invalid,namespace")
        config = load_config()
        assert config.summary_group_by == ["user_id", "namespace"]

    def test_load_workspace_features(self, monkeypatch):
        """Test loading workspace-based feature flags."""
        monkeypatch.setenv("AGENT_MEMORY_USE_WORKSPACE_NAMESPACE", "false")
        monkeypatch.setenv("AGENT_MEMORY_USE_PERSISTENT_SESSION", "false")
        monkeypatch.setenv("AGENT_MEMORY_CREATE_WORKSPACE_SUMMARY", "false")
        monkeypatch.setenv("AGENT_MEMORY_CREATE_SESSION_SUMMARY", "false")

        config = load_config()

        assert config.use_workspace_namespace is False
        assert config.use_persistent_session is False
        assert config.create_workspace_summary is False
        assert config.create_session_summary is False

    def test_workspace_features_default_true(self, monkeypatch):
        """Test that workspace features default to True."""
        # Clear relevant env vars
        for key in [
            "AGENT_MEMORY_USE_WORKSPACE_NAMESPACE",
            "AGENT_MEMORY_USE_PERSISTENT_SESSION",
            "AGENT_MEMORY_CREATE_WORKSPACE_SUMMARY",
            "AGENT_MEMORY_CREATE_SESSION_SUMMARY",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = load_config()

        assert config.use_workspace_namespace is True
        assert config.use_persistent_session is True
        assert config.create_workspace_summary is True
        assert config.create_session_summary is True

    def test_tool_tracking_defaults_off(self, monkeypatch):
        """Test that tool tracking is disabled by default."""
        monkeypatch.delenv("AGENT_MEMORY_TRACK_TOOL_USAGE", raising=False)
        config = load_config()
        assert config.track_tool_usage is False

    def test_tool_tracking_enabled(self, monkeypatch):
        """Test enabling tool tracking via env var."""
        monkeypatch.setenv("AGENT_MEMORY_TRACK_TOOL_USAGE", "true")
        config = load_config()
        assert config.track_tool_usage is True

