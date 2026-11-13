"""Tests for database error diagnostics."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.api.database import (
    classify_db_error,
    describe_db_error,
    sanitize_db_message,
    DB_ERROR_HINTS,
)


class FakeDiag:
    """Имитация psycopg2 DiagnosticMessage."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakePgError(Exception):
    """Имитация исключения psycopg2."""

    def __init__(self, message, pgcode=None, diag=None):
        super().__init__(message)
        self.pgcode = pgcode
        self.diag = diag


class TestClassifyDbError:
    """Проверка классификации ошибок по SQLSTATE и тексту."""

    @pytest.mark.parametrize("sqlstate,expected", [
        ("28P01", "auth_failed"),
        ("3D000", "does_not_exist"),
        ("53300", "too_many_connections"),
        ("57P01", "shutdown"),
        ("42501", "permission_denied"),
        ("08001", "refused"),
        ("08006", "refused"),
        ("XX000", "query_error"),
    ])
    def test_by_sqlstate(self, sqlstate, expected):
        assert classify_db_error(sqlstate, "some error") == expected

    @pytest.mark.parametrize("message,expected", [
        ("connection refused", "refused"),
        ("could not translate host name \"db.local\"", "dns"),
        ("Name or service not known", "dns"),
        ("timeout expired", "timeout"),
        ("password authentication failed for user \"nocodb\"", "auth_failed"),
        ("database \"crm\" does not exist", "does_not_exist"),
        ("sorry, too many clients already", "too_many_connections"),
        ("terminating connection due to administrator command", "shutdown"),
        ("server does not support SSL", "ssl"),
    ])
    def test_by_message(self, message, expected):
        assert classify_db_error(None, message) == expected


class TestDescribeDbError:
    """Проверка формирования описания ошибки."""

    def test_describe_with_diag(self):
        exc = FakePgError(
            'connection to server at "10.0.0.1", port 5432 failed: connection refused',
            pgcode="08001",
            diag=FakeDiag(
                severity="FATAL",
                message_primary="could not connect to server",
                message_detail="Connection refused",
                hint="Is the server running on host and accepting TCP/IP connections?",
                code="08001",
            )
        )
        
        result = describe_db_error(exc)
        
        assert result["kind"] == "refused"
        assert result["sqlstate"] == "08001"
        assert result["severity"] == "FATAL"
        assert result["detail"] == "Connection refused"
        assert result["hint"].startswith("Is the server running")
        assert result["user_hint"] == DB_ERROR_HINTS["refused"]
    
    def test_describe_unicode_error(self):
        result = describe_db_error(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte"))
        
        assert result["kind"] == "encoding"
        assert result["user_hint"] == DB_ERROR_HINTS["encoding"]
    
    def test_unknown_error_has_fallback_hint(self):
        result = describe_db_error(FakePgError("что-то непонятное"))
        
        assert result["kind"] == "query_error"
        assert result["user_hint"]
        assert result["message"] == "что-то непонятное"


class TestSanitizeDbMessage:
    """Хост и пользователь БД не должны попадать в неавторизованные ответы."""

    def test_host_is_masked(self):
        message = 'connection to server at "10.0.0.1", port 5432 failed: connection refused'
        
        sanitized = sanitize_db_message(message)
        
        assert "10.0.0.1" not in sanitized
        assert "<host>" in sanitized
    
    def test_host_with_port_suffix_is_masked(self):
        """Хост в скобках (host (ip)) тоже маскируется."""
        message = 'connection to server at "localhost" (127.0.0.1), port 5432 failed'
        
        sanitized = sanitize_db_message(message)
        
        assert "127.0.0.1" not in sanitized
        assert "localhost" not in sanitized
        assert "<host>" in sanitized
    
    def test_user_is_masked(self):
        message = 'password authentication failed for user "nocodb"'
        
        sanitized = sanitize_db_message(message)
        
        assert "nocodb" not in sanitized
        assert "<user>" in sanitized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
