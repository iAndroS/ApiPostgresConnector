"""Tests for database module."""
import pytest
from unittest.mock import Mock, MagicMock, patch

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.database import Database, parse_dsn


class TestParseDSN:
    """Tests for parse_dsn function."""
    
    def test_parse_dsn_uri_full(self):
        """Test parsing full DSN URI."""
        dsn = "postgres://user:password@localhost:5432/mydb"
        result = parse_dsn(dsn)
        
        assert result['host'] == 'localhost'
        assert result['port'] == 5432
        assert result['database'] == 'mydb'
        assert result['user'] == 'user'
        assert result['password'] == 'password'
    
    def test_parse_dsn_uri_minimal(self):
        """Test parsing minimal DSN URI."""
        dsn = "postgres://localhost/mydb"
        result = parse_dsn(dsn)
        
        assert result['host'] == 'localhost'
        assert result['port'] == 5432
        assert result['database'] == 'mydb'
        assert result['user'] == 'postgres'
        assert result['password'] == ''
    
    def test_parse_dsn_uri_no_password(self):
        """Test DSN without password."""
        dsn = "postgres://user@localhost:5432/mydb"
        result = parse_dsn(dsn)
        
        assert result['user'] == 'user'
        assert result['password'] == ''
    
    def test_parse_dsn_postgresql_prefix(self):
        """Test DSN with postgresql prefix."""
        dsn = "postgresql://user:pass@host:5432/db"
        result = parse_dsn(dsn)
        
        assert result['user'] == 'user'
        assert result['host'] == 'host'
    
    def test_parse_dsn_invalid_format(self):
        """Test invalid DSN format raises error."""
        with pytest.raises(ValueError):
            parse_dsn("invalid-dsn-format")


def make_connected_db(rows=None):
    """Создаёт Database с мокнутым соединением (без реального подключения к БД)."""
    mock_cursor = MagicMock()
    mock_cursor.description = [('id',)]
    mock_cursor.fetchall.return_value = rows if rows is not None else [{'id': 1}]
    
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
    
    with patch("src.api.database.psycopg2.connect", return_value=mock_conn):
        db = Database({'host': 'localhost', 'port': 5432, 'database': 'testdb'})
    
    db.connection = mock_conn
    
    return db, mock_conn, mock_cursor


class TestDatabase:
    """Tests for Database class."""
    
    @patch('src.api.database.psycopg2')
    def test_database_init(self, mock_psycopg2):
        """Test Database initialization."""
        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        
        config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'testdb',
            'user': 'testuser',
            'password': 'testpass'
        }
        
        db = Database(config)
        
        mock_psycopg2.connect.assert_called_once()
        assert db.connection == mock_conn
    
    @patch('src.api.database.psycopg2')
    def test_is_connected_true(self, mock_psycopg2):
        """Test is_connected returns True when connection is open."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        
        db = Database({'host': 'localhost', 'port': 5432, 'database': 'testdb'})
        db.connection = mock_conn
        
        assert db.is_connected() is True
    
    @patch('src.api.database.psycopg2')
    def test_is_connected_false(self, mock_psycopg2):
        """Test is_connected returns False when not connected."""
        mock_psycopg2.Error = Exception
        
        db = Database({'host': 'localhost', 'port': 5432, 'database': 'testdb'})
        db.connection = None
        
        assert db.is_connected() is False
    
    @patch('src.api.database.psycopg2')
    def test_is_connected_closed_socket(self, mock_psycopg2):
        """Закрытое соединение считается отсутствующим (без round-trip до сервера)."""
        mock_conn = MagicMock()
        mock_conn.closed = 1
        
        db = Database({'host': 'localhost', 'port': 5432, 'database': 'testdb'})
        db.connection = mock_conn
        
        assert db.is_connected() is False
    
    @patch('src.api.database.psycopg2')
    def test_get_tables(self, mock_psycopg2):
        """Test get_tables returns list of tables."""
        mock_cursor = MagicMock()
        mock_cursor.description = [('table_name',)]
        mock_cursor.fetchall.return_value = [
            {'table_name': 'users'},
            {'table_name': 'orders'}
        ]
        
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        db = Database({'host': 'localhost', 'port': 5432, 'database': 'testdb'})
        db.connection = mock_conn
        
        result = db.get_tables()
        
        assert result == ['users', 'orders']
    
    @patch('src.api.database.psycopg2')
    def test_get_table_columns(self, mock_psycopg2):
        """Test get_table_columns returns column info."""
        mock_cursor = MagicMock()
        mock_cursor.description = [('column_name',)]
        mock_cursor.fetchall.return_value = [
            {'column_name': 'id', 'data_type': 'integer'},
            {'column_name': 'name', 'data_type': 'varchar'}
        ]
        
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        db = Database({'host': 'localhost', 'port': 5432, 'database': 'testdb'})
        db.connection = mock_conn
        
        result = db.get_table_columns('users')
        
        assert len(result) == 2
        assert result[0]['column_name'] == 'id'
    
    def test_execute_query_returns_rows_for_insert(self):
        """Регрессия: INSERT ... RETURNING должен возвращать вставленные строки."""
        db, mock_conn, mock_cursor = make_connected_db([{'id': 7, 'name': 'test'}])
        
        result = db.execute_query('INSERT INTO "users" ("name") VALUES (%s) RETURNING *', ('test',))
        
        assert result == [{'id': 7, 'name': 'test'}]
        mock_conn.commit.assert_called()
    
    def test_execute_query_without_result_set(self):
        """Запрос без RETURNING возвращает пустой список, а не исключение."""
        db, mock_conn, mock_cursor = make_connected_db()
        mock_cursor.description = None
        
        result = db.execute_query('UPDATE "users" SET "name" = %s', ('x',))
        
        assert result == []
    
    def test_execute_query_records_error(self):
        """Ошибка запроса сохраняется в last_error с понятным описанием."""
        import psycopg2
        
        db, mock_conn, mock_cursor = make_connected_db()
        mock_cursor.execute.side_effect = psycopg2.ProgrammingError('syntax error at or near "SELCT"')
        
        result = db.execute_query('SELCT 1')
        
        assert result is None
        assert db.last_error is not None
        assert db.last_error['message']
        assert db.last_error['kind'] == 'query_error'
        assert db.last_error_message
    
    def test_table_exists(self):
        """Проверка существования таблицы через to_regclass."""
        db, mock_conn, mock_cursor = make_connected_db([{'exists': True}])
        
        assert db.table_exists('users') is True
    
    def test_connect_from_dsn(self):
        """Test connect_from_dsn method."""
        with patch('src.api.database.parse_dsn') as mock_parse, \
             patch('src.api.database.Database._connect') as mock_connect:
            
            mock_parse.return_value = {
                'host': 'localhost',
                'port': 5432,
                'database': 'testdb',
                'user': 'user',
                'password': 'pass'
            }
            
            mock_connect.return_value = None
            
            config = {'host': 'localhost', 'port': 5432, 'database': 'testdb'}
            db = Database(config)
            
            with patch.object(db, 'is_connected', return_value=True):
                result = db.connect_from_dsn("postgres://user:pass@localhost/testdb")
            
            assert result is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
