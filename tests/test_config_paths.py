"""Tests for configuration paths (dev/frozen) and fallback writing."""
import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.config import Config, get_base_dir, get_appdata_dir


class TestBaseDir:
    """Путь к пользовательскому конфигу."""

    def test_dev_mode_uses_project_root(self):
        """В режиме разработки конфиг лежит в корне проекта."""
        expected = Path(__file__).resolve().parent.parent
        
        assert get_base_dir() == expected
        assert (get_base_dir() / "config" / "settings.json").exists()

    def test_frozen_mode_uses_executable_dir(self, monkeypatch, tmp_path):
        """В собранном приложении конфиг лежит рядом с EXE."""
        fake_exe = tmp_path / "ApiPostgresConnector.exe"
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(fake_exe))
        
        assert get_base_dir() == fake_exe.resolve().parent

    def test_config_path_follows_base_dir(self, monkeypatch, tmp_path):
        """Config использует путь рядом с EXE в frozen-режиме."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "app.exe"))
        
        with patch.object(Config, 'load'):
            config = Config()
        
        assert config._config_path == tmp_path / "config" / "settings.json"


class TestAppdataFallback:
    """Fallback в %APPDATA%, если рядом с EXE нет прав на запись."""

    def test_appdata_dir_uses_env(self, monkeypatch):
        monkeypatch.setenv("APPDATA", r"C:\Users\tester\AppData\Roaming")
        
        appdata = get_appdata_dir()
        
        assert appdata.name == "ApiPostgresConnector"
        assert appdata.parent.name == "Roaming"

    def test_save_falls_back_when_permission_denied(self, monkeypatch, tmp_path):
        """При отказе в правах конфиг сохраняется в %APPDATA%."""
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
        
        config = Config.__new__(Config)
        config._base_path = tmp_path
        config._config_path = tmp_path / "config" / "settings.json"
        config._fallback_path = get_appdata_dir() / "config" / "settings.json"
        config._config = {
            "connections": [{
                "name": "main",
                "database": {"password": ""},
                "api_keys": []
            }],
            "default_connection": "main",
            "api": {}, "gui": {}, "app": {}
        }
        
        written = []
        real_write = Config._atomic_write
        
        def fake_write(path, content):
            written.append(Path(path))
            if len(written) == 1:
                raise PermissionError("read-only file system")
            real_write(path, content)
        
        with patch.object(Config, "_atomic_write", side_effect=fake_write):
            config.save()
        
        assert len(written) == 2
        assert written[0] == tmp_path / "config" / "settings.json"
        assert written[1] == tmp_path / "Roaming" / "ApiPostgresConnector" / "config" / "settings.json"
        assert written[1].exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
