"""Тесты переключателя «Требовать API-ключ» и страницы-«пробника» /try."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.api.connections import ConnectionRegistry


class FakeConfig:
    """Конфиг с переключателем авторизации."""

    def __init__(self, require_auth=True):
        self.connections = [{
            "name": "main",
            "database": {"host": "localhost", "port": 5432, "database": "db", "user": "u", "password": ""},
            "api_keys": ["secret-key"]
        }]
        self.default_connection = "main"
        self.api = {"host": "127.0.0.1", "port": 5000, "require_auth": require_auth}


@pytest.fixture
def client_factory():
    """Создаёт Flask-клиент с указанным режимом авторизации."""
    from flask import Flask
    from src.api.routes import api_bp, init_routes

    def factory(require_auth=True):
        registry = ConnectionRegistry(FakeConfig(require_auth))
        
        from unittest.mock import MagicMock
        mock_db = MagicMock()
        mock_db.is_connected.return_value = True
        mock_db.get_tables.return_value = ["users"]
        mock_db.get_last_error.return_value = None
        registry.get("main").set_db(mock_db)
        
        app = Flask(__name__)
        init_routes(registry)
        app.register_blueprint(api_bp)
        app.config["TESTING"] = True
        
        return app.test_client(), registry
    
    return factory


class TestRequireAuthSwitch:
    """Переключатель обязательности API-ключа."""

    def test_auth_required_by_default(self, client_factory):
        """По умолчанию запрос без ключа отклоняется."""
        client, _ = client_factory(require_auth=True)
        
        response = client.get('/api/v1/tables')
        
        assert response.status_code == 401
        assert 'Missing API key' in response.get_json()['error']

    def test_auth_disabled_allows_request_without_key(self, client_factory):
        """С выключенной авторизацией запрос выполняется без ключа."""
        client, _ = client_factory(require_auth=False)
        
        response = client.get('/api/v1/tables')
        
        assert response.status_code == 200
        assert response.get_json()['tables'] == ['users']

    def test_info_reports_auth_disabled(self, client_factory):
        """/info показывает, что авторизация не требуется."""
        client, _ = client_factory(require_auth=False)
        
        data = client.get('/api/v1/info').get_json()
        
        assert data['auth_required'] is False
        assert data['api_key_count'] == 1

    def test_registry_reads_switch_from_config(self):
        """Реестр читает переключатель из конфига."""
        registry = ConnectionRegistry(FakeConfig(require_auth=False))
        
        assert registry.require_auth is False
        
        registry.reload(FakeConfig(require_auth=True))
        assert registry.require_auth is True


class TestTryPage:
    """Страница-«пробник» для проверки запросов из браузера."""

    def test_try_page_renders(self, client_factory):
        """Страница /try отдаёт HTML с путём и ключом."""
        from src.app import APIServer
        
        client, _ = client_factory(require_auth=True)
        
        # Используем приложение из app.py, чтобы проверить сам маршрут
        server = APIServer()
        app = server._create_app("127.0.0.1", 5055)
        
        with app.test_client() as test_client:
            response = test_client.get('/try?path=%2Fapi%2Fv1%2Ftables')
            
            assert response.status_code == 200
            body = response.get_data(as_text=True)
            assert '/api/v1/tables' in body
            assert 'X-API-Key' in body

    def test_try_page_rejects_non_api_path(self):
        """Не-API путь заменяется на безопасный /health."""
        from src.app import APIServer
        
        server = APIServer()
        app = server._create_app("127.0.0.1", 5056)
        
        with app.test_client() as test_client:
            response = test_client.get('/try?path=%2Fetc%2Fpasswd')
            
            assert response.status_code == 200
            body = response.get_data(as_text=True)
            assert '/etc/passwd' not in body
            assert '/api/v1/health' in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
