"""Database module for PostgreSQL operations."""
import logging
import os
import re
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Set PostgreSQL client encoding to UTF-8 to avoid encoding issues on Windows
# This must be done before any connection is made
os.environ.setdefault('PGCLIENTENCODING', 'UTF8')


def parse_dsn(dsn: str) -> dict:
    """Парсит строку подключения postgres://user:pass@host:port/db.
    
    Args:
        dsn: Строка подключения в формате postgres://user:pass@host:port/database
        
    Returns:
        dict: Словарь с параметрами подключения (host, port, database, user, password)
    """
    # Поддерживаемые форматы:
    # postgres://user:pass@host:port/db
    # postgresql://user:pass@host:port/db
    # user=xxx password=xxx host=xxx port=xxx dbname=xxx
    
    result: Dict[str, Any] = {}
    dsn = dsn.strip()
    
    # Проверяем формат URI
    uri_match = re.match(
        r'^(?:postgres|postgresql)://(?:(?P<user>[^:@]+)(?::(?P<password>[^@]*))?@)?(?:(?P<host>[^:/]+)(?::(?P<port>\d+))?)(?:/(?P<database>.*))?$',
        dsn
    )
    
    if uri_match:
        groups = uri_match.groupdict()
        result['host'] = groups.get('host', 'localhost') or 'localhost'
        result['port'] = int(groups.get('port', 5432)) if groups.get('port') else 5432
        result['database'] = groups.get('database', '') or 'postgres'
        result['user'] = groups.get('user', 'postgres') or 'postgres'
        result['password'] = groups.get('password', '') or ''
        return result
    
    # Пробуем формат с именованными параметрами (key=value)
    param_match = re.match(
        r'^(?:.*\s+)?user=(?P<user>[^\s]+)(?:\s+password=(?P<password>[^\s]+))?(?:\s+host=(?P<host>[^\s]+))?(?:\s+port=(?P<port>\d+))?(?:\s+dbname=(?P<database>[^\s]+))?',
        dsn
    )
    
    if param_match:
        groups = param_match.groupdict()
        result['host'] = groups.get('host', 'localhost') or 'localhost'
        result['port'] = int(groups.get('port', 5432)) if groups.get('port') else 5432
        result['database'] = groups.get('database', '') or 'postgres'
        result['user'] = groups.get('user', 'postgres') or 'postgres'
        result['password'] = groups.get('password', '') or ''
        return result
    
    raise ValueError(f"Invalid DSN format: {dsn}")


class Database:
    """PostgreSQL database connection manager."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection = None
        self._connect()

    def connect_from_dsn(self, dsn_string: str) -> bool:
        """Подключение к БД используя DSN строку.
        
        Args:
            dsn_string: Строка подключения в формате 
                       postgres://user:pass@host:port/database
        
        Returns:
            bool: True при успешном подключении
        """
        try:
            parsed = parse_dsn(dsn_string)
            self.config = parsed
            self._connect()
            return self.is_connected()
        except Exception as e:
            logger.error(f"Failed to connect using DSN: {e}")
            return False

    def _connect(self):
        """Establish database connection."""
        try:
            logger.debug(f"Connecting to database: host={self.config.get('host')}, "
                        f"port={self.config.get('port')}, database={self.config.get('database')}, "
                        f"user={self.config.get('user')}")
            
            self.connection = psycopg2.connect(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 5432),
                database=self.config.get("database", "zenno_db"),
                user=self.config.get("user", "postgres"),
                password=self.config.get("password", ""),
                cursor_factory=RealDictCursor
            )
            logger.info("Database connection established")
        except UnicodeDecodeError as e:
            # This can happen on Windows with non-UTF8 locale (e.g., Russian_Russia.1251)
            logger.error(f"UnicodeDecodeError in database connection: {e}")
            logger.error(f"This may be caused by encoding mismatch. "
                        f"Try setting PGCLIENTENCODING=UTF8 environment variable.")
            logger.debug(f"Config values: host={self.config.get('host')}, "
                        f"database={self.config.get('database')}, user={self.config.get('user')}")
            self.connection = None
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            self.connection = None

    def is_connected(self) -> bool:
        """Check if database is connected."""
        if self.connection is None:
            return False
        try:
            self.connection.cursor().execute("SELECT 1")
            return True
        except psycopg2.Error:
            return False

    def reconnect(self):
        """Reconnect to database."""
        if self.connection:
            self.connection.close()
        self._connect()

    def execute_query(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict]]:
        """Execute SELECT query and return results."""
        if not self.is_connected():
            self.reconnect()
            if not self.is_connected():
                logger.error("Cannot execute query: not connected to database")
                return None

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                if query.strip().upper().startswith("SELECT"):
                    return cursor.fetchall()
                self.connection.commit()
                return []
        except psycopg2.Error as e:
            logger.error(f"Query execution failed: {e}")
            self.connection.rollback()
            return None

    def execute_update(self, query: str, params: Optional[tuple] = None) -> bool:
        """Execute INSERT/UPDATE/DELETE query."""
        if not self.is_connected():
            self.reconnect()
            if not self.is_connected():
                logger.error("Cannot execute update: not connected to database")
                return False

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                return True
        except psycopg2.Error as e:
            logger.error(f"Update execution failed: {e}")
            self.connection.rollback()
            return False

    def get_tables(self) -> List[str]:
        """Get list of all tables in database."""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        result = self.execute_query(query)
        if result:
            return [row["table_name"] for row in result]
        return []

    def get_table_columns(self, table_name: str) -> List[Dict]:
        """Get columns for specified table."""
        query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """
        result = self.execute_query(query, (table_name,))
        return result if result else []

    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
