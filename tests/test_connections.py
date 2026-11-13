"""Tests for the connection registry."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import MagicMock

from src.api.connections import ConnectionRegistry, ConnectionProfile, db_signature


class FakeConfig:
    """Минимальный конфиг для тестов реестра."""

    def __init__(self, connections, default_connection=None):
        self.connections = connections
        self.default_connection = default_connection or (
            connections[0]["name"] if connections else ""
        )


def make_connection(name, host="localhost", api_keys=None):
    return {
        "name": name,
        "database": {
            "host": host,
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": ""
        },
        "api_keys": list(api_keys) if api_keys else []
    }


class TestConnectionProfile:
    """Tests for ConnectionProfile."""

    def test_has_key(self):
        profile = ConnectionProfile("main", {}, ["key-a"])
        
        assert profile.has_key("key-a") is True
        assert profile.has_key("key-b") is False
        assert profile.has_key("") is False

    def test_signature_changes_with_params(self):
        profile = ConnectionProfile("main", {"host": "a", "port": 5432}, [])
        other = ConnectionProfile("main", {"host": "b", "port": 5432}, [])
        
        assert profile.signature() != other.signature()
        assert profile.signature() == db_signature({"host": "a", "port": 5432})


class TestConnectionRegistry:
    """Tests for ConnectionRegistry."""

    def test_builds_profiles(self):
        config = FakeConfig(
            [make_connection("main", api_keys=["k1"]), make_connection("crm", api_keys=["k2"])],
            default_connection="main"
        )
        
        registry = ConnectionRegistry(config)
        
        assert registry.names() == ["main", "crm"]
        assert registry.default_name == "main"
        assert registry.get("crm").api_keys == ["k2"]
        assert registry.get_default().name == "main"
        assert registry.get("missing") is None
        assert registry.total_key_count() == 2

    def test_reload_adds_connection(self):
        config = FakeConfig([make_connection("main")], default_connection="main")
        registry = ConnectionRegistry(config)
        
        config.connections.append(make_connection("crm"))
        registry.reload(config)
        
        assert registry.names() == ["main", "crm"]

    def test_reload_removes_connection(self):
        config = FakeConfig(
            [make_connection("main"), make_connection("crm")],
            default_connection="main"
        )
        registry = ConnectionRegistry(config)
        
        removed = registry.get("crm")
        config.connections = [make_connection("main")]
        registry.reload(config)
        
        assert registry.names() == ["main"]
        assert removed.is_db_created is False

    def test_reload_keeps_database_when_params_unchanged(self):
        config = FakeConfig([make_connection("main")], default_connection="main")
        registry = ConnectionRegistry(config)
        
        profile = registry.get("main")
        profile.set_db(MagicMock())
        
        config.connections[0]["api_keys"] = ["new-key"]
        registry.reload(config)
        
        # Тот же объект подключения, но ключи обновились
        assert registry.get("main") is profile
        assert profile.api_keys == ["new-key"]
        assert profile.is_db_created is True

    def test_reload_recreates_database_when_params_changed(self):
        config = FakeConfig([make_connection("main")], default_connection="main")
        registry = ConnectionRegistry(config)
        
        profile = registry.get("main")
        profile.set_db(MagicMock())
        
        config.connections[0]["database"]["host"] = "new-host"
        registry.reload(config)
        
        assert registry.get("main") is not profile
        assert registry.get("main").is_db_created is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
