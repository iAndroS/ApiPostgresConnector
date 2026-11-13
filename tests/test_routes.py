"""Tests for API routes."""
import pytest
from unittest.mock import MagicMock

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.connections import ConnectionRegistry
from src.api.routes import (
    api_bp,
    init_routes,
    validate_identifier,
    require_api_key
)


class FakeConfig:
    """Минимальный конфиг для тестов реестра подключений."""

    def __init__(self, connections):
        self.connections = connections

    @property
    def database(self):
        return self.connections[0]["database"] if self.connections else {}


def make_connection(name, api_keys, host="localhost"):
    return {
        "name": name,
        "database": {
            "host": host,
            "port": 5432,
            "database": "testdb",
            "user": "testuser",
            "password": ""
        },
        "api_keys": list(api_keys)
    }


def make_registry():
    """Создаёт реестр с двумя подключениями и мокнутыми базами."""
    config = FakeConfig(
        [
            make_connection("main", ["key-main"]),
            make_connection("other", ["key-other"], host="other-host")
        ]
    )
    
    registry = ConnectionRegistry(config)
    
    for profile in registry.names():
        registry.get(profile).set_db(make_mock_db())
    
    return registry


def make_mock_db():
    """Мок базы данных: to_regclass → таблица существует, остальное → одна строка."""
    mock_db = MagicMock()
    mock_db.is_connected.return_value = True
    mock_db.get_tables.return_value = ["users", "orders"]
    mock_db.get_last_error.return_value = None
    mock_db.last_error_message = None
    mock_db.table_exists.return_value = True
    
    def fake_execute(query, params=None):
        if "to_regclass" in query:
            return [{"exists": True}]
        return [{"id": 1, "name": "test"}]
    
    mock_db.execute_query.side_effect = fake_execute
    mock_db.execute_update.return_value = True
    mock_db.execute_batch.return_value = [{"id": 1}, {"id": 2}]
    
    return mock_db


@pytest.fixture
def registry():
    """Реестр подключений с мокнутыми базами."""
    return make_registry()


@pytest.fixture
def client(registry):
    """Create test client."""
    from flask import Flask
    
    app = Flask(__name__)
    init_routes(registry)
    app.register_blueprint(api_bp)
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        yield client


class TestValidateIdentifier:
    """Tests for validate_identifier function."""
    
    def test_valid_identifiers(self):
        """Test valid SQL identifiers."""
        assert validate_identifier('users') is True
        assert validate_identifier('user_data') is True
        assert validate_identifier('_private') is True
        assert validate_identifier('table123') is True
    
    def test_invalid_identifiers(self):
        """Test invalid SQL identifiers."""
        assert validate_identifier('') is False
        assert validate_identifier('123table') is False
        assert validate_identifier('table-name') is False
        assert validate_identifier('table name') is False
        assert validate_identifier(None) is False


class TestApiRoutes:
    """Tests for API routes."""
    
    def test_health_check_no_auth(self, client):
        """Health endpoint doesn't require auth."""
        response = client.get('/api/v1/c/main/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        assert data['connection'] == 'main'
        # Состояние подключения реальное, а не всегда false
        assert data['database_connected'] is True
    
    def test_health_reports_real_connection_state(self, registry):
        """Health отдаёт фактическое состояние подключения (а не всегда false)."""
        from flask import Flask
        
        app = Flask(__name__)
        init_routes(registry)
        app.register_blueprint(api_bp)
        
        with app.test_client() as client:
            response = client.get('/api/v1/c/main/health')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['database_connected'] is True
    
    def test_health_does_not_block_on_database(self, registry):
        """Health не ждёт подключения к БД (иначе мониторинг встанет)."""
        from flask import Flask
        import time
        
        profile = registry.get('main')
        profile._db = None
        
        app = Flask(__name__)
        init_routes(registry)
        app.register_blueprint(api_bp)
        
        with app.test_client() as client:
            started = time.monotonic()
            response = client.get('/api/v1/c/main/health')
            elapsed = time.monotonic() - started
            
            assert response.status_code == 200
            assert elapsed < 2, f"Health отвечал {elapsed:.1f} с — он ждёт подключения к БД"
    
    def test_health_reports_failure_reason(self, registry):
        """При недоступной БД health отдаёт причину ошибки."""
        from flask import Flask
        
        profile = registry.get('main')
        mock_db = MagicMock()
        mock_db.is_connected.return_value = False
        mock_db.get_last_error.return_value = {
            "kind": "auth_failed",
            "message": 'password authentication failed for user "secretuser"',
            "detail": None,
            "hint": None,
            "sqlstate": "28P01",
            "severity": "FATAL",
            "user_hint": "Неверный пользователь или пароль",
        }
        profile.set_db(mock_db)
        profile.db.should_retry_connect.return_value = False
        
        app = Flask(__name__)
        init_routes(registry)
        app.register_blueprint(api_bp)
        
        with app.test_client() as client:
            response = client.get('/api/v1/c/main/health')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['database_connected'] is False
            assert data['last_error']['kind'] == 'auth_failed'
            # Имя пользователя в публичном ответе не раскрывается
            assert "secretuser" not in data['last_error']['message']
    
    def test_api_info_no_auth(self, client):
        """Info endpoint doesn't require auth."""
        response = client.get('/api/v1/c/main/info')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'ApiPostgresConnector' in data['name']
        assert data['api_key_count'] == 2
        assert data['auth_required'] is True
    
    def test_tables_requires_auth_with_keys(self, client):
        """Tables endpoint requires auth when keys are set."""
        response = client.get('/api/v1/c/main/tables')
        
        assert response.status_code == 401
        assert 'Missing API key' in response.get_json()['error']
    
    def test_tables_with_invalid_key(self, client):
        """Tables endpoint rejects an unknown key."""
        response = client.get('/api/v1/c/main/tables', headers={'X-API-Key': 'nope'})
        
        assert response.status_code == 401
        assert 'Invalid API key' in response.get_json()['error']
    
    def test_tables_with_valid_auth(self, client):
        """Tables endpoint works with valid auth."""
        response = client.get(
            '/api/v1/c/main/tables',
            headers={'X-API-Key': 'key-main'}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'tables' in data
        assert data['connection'] == 'main'
    
    def test_key_is_bound_to_its_connection(self, client):
        """Ключ одного подключения не работает для другого."""
        response = client.get(
            '/api/v1/c/main/tables',
            headers={'X-API-Key': 'key-other'}
        )
        
        assert response.status_code == 401
        assert 'Invalid API key for connection "main"' in response.get_json()['error']
    
    def test_named_connection_works(self, client):
        """Именованное подключение доступно по своему ключу."""
        response = client.get(
            '/api/v1/c/other/tables',
            headers={'X-API-Key': 'key-other'}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['connection'] == 'other'
    
    def test_unknown_connection_returns_404(self, client):
        """Неизвестное имя подключения — 404."""
        response = client.get(
            '/api/v1/c/nope/tables',
            headers={'X-API-Key': 'key-main'}
        )
        
        assert response.status_code == 404
        assert 'Unknown connection' in response.get_json()['error']
    
    def test_disabled_connection_returns_403(self, client, registry):
        """Отключённое подключение не обслуживается — 403."""
        registry.get("other").enabled = False
        
        response = client.get(
            '/api/v1/c/other/tables',
            headers={'X-API-Key': 'key-other'}
        )
        
        assert response.status_code == 403
        assert 'disabled' in response.get_json()['error']
    
    def test_disabled_connection_health_returns_403(self, client, registry):
        """Отключённое подключение — 403 даже для /health."""
        registry.get("main").enabled = False
        
        response = client.get('/api/v1/c/main/health')
        
        assert response.status_code == 403
    
    def test_request_without_connection_name_returns_404(self, client):
        """Без имени подключения запрос не обслуживается."""
        response = client.get(
            '/api/v1/tables',
            headers={'X-API-Key': 'key-main'}
        )
        
        assert response.status_code == 404
        assert 'Укажите подключение' in response.get_json()['error']
    
    def test_query_select_only(self, client):
        """Query endpoint only allows SELECT."""
        response = client.post(
            '/api/v1/c/main/query',
            json={'query': 'SELECT * FROM users'},
            headers={'X-API-Key': 'key-main'}
        )
        assert response.status_code == 200
    
    def test_query_block_non_select(self, client):
        """Query endpoint blocks non-SELECT queries."""
        response = client.post(
            '/api/v1/c/main/query',
            json={'query': 'INSERT INTO users VALUES (1)'},
            headers={'X-API-Key': 'key-main'}
        )
        assert response.status_code == 403
    
    def test_table_columns_validates_name(self, client):
        """Table columns validates identifier."""
        response = client.get(
            '/api/v1/c/main/tables/table--name/columns',
            headers={'X-API-Key': 'key-main'}
        )
        assert response.status_code == 400
    
    def test_insert_validates_column_names(self, client):
        """Insert validates column names."""
        response = client.post(
            '/api/v1/c/main/tables/users/insert',
            json={'123name': 'value'},
            headers={'X-API-Key': 'key-main'}
        )
        assert response.status_code == 400
    
    def test_insert_returns_inserted_row(self, client):
        """INSERT возвращает вставленную строку (регрессия: раньше был IndexError → 500)."""
        response = client.post(
            '/api/v1/c/main/tables/users/insert',
            json={'name': 'test'},
            headers={'X-API-Key': 'key-main'}
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['data'] == {'id': 1, 'name': 'test'}
    
    def test_insert_requires_object(self, client):
        """INSERT с массивом вместо объекта — 400, а не 500."""
        response = client.post(
            '/api/v1/c/main/tables/users/insert',
            json=[{'name': 'test'}],
            headers={'X-API-Key': 'key-main'}
        )
        assert response.status_code == 400
    
    def test_batch_insert_returns_rows(self, client):
        """Batch insert returns inserted rows."""
        response = client.post(
            '/api/v1/c/main/tables/users/batch-insert',
            json=[{'name': 'a'}, {'name': 'b'}],
            headers={'X-API-Key': 'key-main'}
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['inserted'] == 2
    
    def test_batch_insert_rejects_different_columns(self, client):
        """Строки с разными наборами колонок — 400 (иначе данные теряются молча)."""
        response = client.post(
            '/api/v1/c/main/tables/users/batch-insert',
            json=[{'name': 'a'}, {'other': 'b'}],
            headers={'X-API-Key': 'key-main'}
        )
        
        assert response.status_code == 400
        assert 'different columns' in response.get_json()['error']


class TestRequireApiKey:
    """Tests for require_api_key decorator."""
    
    def test_missing_key(self, registry):
        """Test request without API key."""
        from flask import Flask
        from src.api.routes import require_api_key
        
        app = Flask(__name__)
        init_routes(registry)
        
        @app.route('/test/<connection_name>')
        @require_api_key
        def test_endpoint(connection_name):
            return {'status': 'ok'}
        
        with app.test_client() as client:
            response = client.get('/test/main')
            assert response.status_code == 401
            assert 'Missing API key' in response.get_json()['error']
    
    def test_invalid_key(self, registry):
        """Test request with invalid API key."""
        from flask import Flask
        from src.api.routes import require_api_key
        
        app = Flask(__name__)
        init_routes(registry)
        
        @app.route('/test/<connection_name>')
        @require_api_key
        def test_endpoint(connection_name):
            return {'status': 'ok'}
        
        with app.test_client() as client:
            response = client.get('/test/main', headers={'X-API-Key': 'invalid-key'})
            assert response.status_code == 401
            assert 'Invalid API key' in response.get_json()['error']
    
    def test_valid_key(self, registry):
        """Test request with valid API key."""
        from flask import Flask
        from src.api.routes import require_api_key
        
        app = Flask(__name__)
        init_routes(registry)
        
        @app.route('/test/<connection_name>')
        @require_api_key
        def test_endpoint(connection_name):
            return {'status': 'ok'}
        
        with app.test_client() as client:
            response = client.get('/test/main', headers={'X-API-Key': 'key-main'})
            assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
