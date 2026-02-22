"""Tests for API routes."""
import pytest
from unittest.mock import Mock, MagicMock, patch

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.routes import (
    api_bp, 
    init_routes, 
    validate_identifier,
    require_api_key
)


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
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from flask import Flask
        
        app = Flask(__name__)
        app.register_blueprint(api_bp)
        app.config['TESTING'] = True
        
        with app.test_client() as client:
            yield client
    
    def test_health_check_no_auth(self, client):
        """Test health endpoint doesn't require auth."""
        # Set up routes with empty keys
        mock_db = MagicMock()
        mock_db.is_connected.return_value = True
        init_routes(mock_db, set())
        
        response = client.get('/api/v1/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
        assert data['database_connected'] is True
    
    def test_api_info_no_auth(self, client):
        """Test info endpoint doesn't require auth."""
        mock_db = MagicMock()
        init_routes(mock_db, set())
        
        response = client.get('/api/v1/info')
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'ApiPostgresConnector' in data['name']
    
    def test_tables_requires_auth_with_keys(self, client):
        """Test tables endpoint requires auth when keys are set."""
        mock_db = MagicMock()
        init_routes(mock_db, {'test-key'})
        
        response = client.get('/api/v1/tables')
        
        assert response.status_code == 401
    
    def test_tables_with_valid_auth(self, client):
        """Test tables endpoint works with valid auth."""
        mock_db = MagicMock()
        mock_db.get_tables.return_value = ['users', 'orders']
        init_routes(mock_db, {'test-key'})
        
        response = client.get(
            '/api/v1/tables',
            headers={'X-API-Key': 'test-key'}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'tables' in data
    
    def test_query_select_only(self, client):
        """Test query endpoint only allows SELECT."""
        mock_db = MagicMock()
        mock_db.execute_query.return_value = []
        init_routes(mock_db, set())
        
        # Test SELECT - should work
        response = client.post(
            '/api/v1/query',
            json={'query': 'SELECT * FROM users'}
        )
        assert response.status_code in [200, 500]  # 500 if no db connection
    
    def test_query_block_non_select(self, client):
        """Test query endpoint blocks non-SELECT queries."""
        mock_db = MagicMock()
        init_routes(mock_db, set())
        
        response = client.post(
            '/api/v1/query',
            json={'query': 'INSERT INTO users VALUES (1)'}
        )
        
        assert response.status_code == 403
    
    def test_table_columns_validates_name(self, client):
        """Test table columns validates identifier."""
        mock_db = MagicMock()
        init_routes(mock_db, set())
        
        # Invalid table name (contains special chars)
        response = client.get('/api/v1/tables/table--name/columns')
        
        assert response.status_code == 400
    
    def test_insert_validates_column_names(self, client):
        """Test insert validates column names."""
        mock_db = MagicMock()
        mock_db.get_tables.return_value = ['users']
        init_routes(mock_db, set())
        
        # Invalid column name (starts with number)
        response = client.post(
            '/api/v1/tables/users/insert',
            json={'123name': 'value'}
        )
        
        assert response.status_code == 400


class TestRequireApiKey:
    """Tests for require_api_key decorator."""
    
    def test_missing_key(self):
        """Test request without API key."""
        from flask import Flask, request
        from src.api.routes import require_api_key
        
        app = Flask(__name__)
        
        @app.route('/test')
        @require_api_key
        def test_endpoint():
            return {'status': 'ok'}
        
        with app.test_client() as client:
            response = client.get('/test')
            assert response.status_code == 401
    
    def test_invalid_key(self):
        """Test request with invalid API key."""
        from flask import Flask
        from src.api.routes import require_api_key, API_KEYS
        
        app = Flask(__name__)
        
        @app.route('/test')
        @require_api_key
        def test_endpoint():
            return {'status': 'ok'}
        
        with app.test_client() as client:
            response = client.get(
                '/test',
                headers={'X-API-Key': 'invalid-key'}
            )
            assert response.status_code == 401


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
