"""Тесты экспорта/импорта настроек подключений."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Изолированный конфиг (файлы не трогают рабочий settings.json)."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from src.config import Config

    with patch.object(Config, 'load'):
        instance = Config()

    instance._config_path = Path(tempfile.gettempdir()) / "api_postgres_connector_export_test.json"
    instance._fallback_path = instance._config_path
    instance._config = {
        "connections": [
            {
                "name": "Основное",
                "database": {"host": "h1", "port": 5432, "database": "d1",
                             "user": "u1", "password": "p1"},
                "api_keys": ["key-1"],
                "enabled": True,
            },
            {
                "name": "Второе",
                "database": {"host": "h2", "port": 5432, "database": "d2",
                             "user": "u2", "password": "p2"},
                "api_keys": ["key-2"],
                "enabled": False,
            },
        ],
        "api": {},
    }

    return instance


def test_export_writes_file(config, tmp_path):
    """Экспорт создаёт файл со всеми подключениями."""
    target = tmp_path / "export.json"
    
    count = config.export_connections(str(target))
    
    assert count == 2
    assert target.exists()
    
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["connections"]) == 2
    
    first = data["connections"][0]
    assert first["name"] == "Основное"
    assert first["database"]["host"] == "h1"
    assert first["api_keys"] == ["key-1"]
    assert first["enabled"] is True


def test_import_adds_new_connections(config, tmp_path):
    """Импорт добавляет новые подключения."""
    source = tmp_path / "import.json"
    source.write_text(json.dumps({
        "version": 1,
        "connections": [
            {
                "name": "Третье",
                "database": {"host": "h3", "port": 5432, "database": "d3",
                             "user": "u3", "password": "p3"},
                "api_keys": ["key-3"],
                "enabled": True,
            }
        ]
    }, ensure_ascii=False), encoding="utf-8")
    
    result = config.import_connections(str(source))
    
    assert result["added"] == ["Третье"]
    assert config.get_connection("Третье")["database"]["host"] == "h3"


def test_import_updates_existing(config, tmp_path):
    """Импорт обновляет существующее подключение с тем же именем."""
    source = tmp_path / "import.json"
    source.write_text(json.dumps({
        "connections": [
            {
                "name": "Основное",
                "database": {"host": "new-host"},
                "api_keys": ["new-key"],
                "enabled": False,
            }
        ]
    }, ensure_ascii=False), encoding="utf-8")
    
    result = config.import_connections(str(source))
    
    assert result["updated"] == ["Основное"]
    
    connection = config.get_connection("Основное")
    assert connection["database"]["host"] == "new-host"
    assert connection["api_keys"] == ["new-key"]
    assert connection["enabled"] is False
    assert len(config.connections) == 2


def test_import_skips_invalid(config, tmp_path):
    """Записи без имени пропускаются."""
    source = tmp_path / "import.json"
    source.write_text(json.dumps({
        "connections": [{"name": ""}, {"name": "Новое"}]
    }, ensure_ascii=False), encoding="utf-8")
    
    result = config.import_connections(str(source))
    
    assert result["added"] == ["Новое"]
    assert len(result["skipped"]) == 1


def test_import_rejects_wrong_format(config, tmp_path):
    """Файл без подключений — понятная ошибка."""
    source = tmp_path / "bad.json"
    source.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    
    with pytest.raises(ValueError):
        config.import_connections(str(source))


def test_export_import_roundtrip(config, tmp_path):
    """Экспорт → импорт в другой конфиг сохраняет настройки."""
    import tempfile
    from pathlib import Path

    target = tmp_path / "export.json"
    config.export_connections(str(target))
    
    from unittest.mock import patch

    from src.config import Config

    with patch.object(Config, 'load'):
        other = Config()
    other._config_path = Path(tempfile.gettempdir()) / "api_postgres_connector_export_test2.json"
    other._fallback_path = other._config_path
    other._config = {"connections": [], "api": {}}
    
    result = other.import_connections(str(target))
    
    assert len(result["added"]) == 2
    assert result["updated"] == []
    assert other.get_connection("Второе")["enabled"] is False
    assert other.get_connection("Основное")["database"]["password"] == "p1"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
