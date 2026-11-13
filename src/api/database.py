"""Database module for PostgreSQL operations."""
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Set PostgreSQL client encoding to UTF8 - must be done before any connection is made
os.environ.setdefault('PGCLIENTENCODING', 'UTF8')

# Таймаут подключения к БД (секунды) — чтобы GUI не зависал на недоступном хосте
CONNECT_TIMEOUT = 10

# Пауза перед повторной попыткой подключения после неудачи (секунды).
# Без неё каждый запрос к недоступной БД тратил бы 2 × CONNECT_TIMEOUT.
RECONNECT_COOLDOWN = 30.0

# Имя приложения в pg_stat_activity — чтобы соединения было видно в списке на стороне БД
APPLICATION_NAME = "ApiPostgresConnector"

# Человекочитаемые подсказки по типам ошибок
DB_ERROR_HINTS: Dict[str, str] = {
    "auth_failed": "Неверный пользователь или пароль",
    "permission_denied": "Нет прав на операцию — проверьте привилегии пользователя БД",
    "refused": "PostgreSQL не принимает соединения на этом порту — проверьте, что сервис запущен и порт указан верно",
    "dns": "Не удалось разрешить имя хоста — проверьте DNS и сетевой доступ",
    "timeout": "Сервер БД не отвечает — проверьте доступность хоста и правила файрвола",
    "does_not_exist": "База данных не существует — проверьте её имя",
    "too_many_connections": "Превышен лимит одновременных соединений к БД",
    "shutdown": "Соединение закрыто администратором базы данных",
    "ssl": "Ошибка SSL-соединения — проверьте sslmode и сертификаты сервера",
    "encoding": "Ошибка кодировки — проверьте PGCLIENTENCODING=UTF8",
    "query_error": "Ошибка выполнения запроса — подробности (detail/hint) в app.log",
    "unknown": "Причина не распознана — полные детали в app.log",
}


def _diag_value(exc: BaseException, attribute: str) -> Optional[str]:
    """Достаёт поле из psycopg2 DiagnosticMessage (diag)."""
    diag = getattr(exc, "diag", None)
    if diag is None:
        return None
    value = getattr(diag, attribute, None)
    return str(value) if value else None


def classify_db_error(sqlstate: Optional[str], message: str) -> str:
    """Определяет тип ошибки PostgreSQL.

    Args:
        sqlstate: SQLSTATE-код (pgcode) или None
        message: Текст ошибки

    Returns:
        Ключ из DB_ERROR_HINTS
    """
    text = (message or "").lower()
    state = (sqlstate or "").upper()
    
    if "timeout expired" in text or "no response from server" in text:
        return "timeout"
    if ("could not translate host name" in text or "name or service not known" in text
            or "nodename nor servname" in text or "getaddrinfo failed" in text):
        return "dns"
    if ("connection refused" in text or "no connection to the server" in text
            or "could not connect to server" in text or "connection was closed" in text):
        return "refused"
    if ("password authentication failed" in text or "authentication failed" in text
            or "no password supplied" in text):
        return "auth_failed"
    if "permission denied" in text:
        return "permission_denied"
    if "does not exist" in text and "database" in text:
        return "does_not_exist"
    if "too many clients" in text or "too many connections" in text:
        return "too_many_connections"
    if "terminating connection" in text or "server closed the connection" in text:
        return "shutdown"
    if "ssl" in text and ("error" in text or "not support" in text):
        return "ssl"
    
    if state == "28P01":
        return "auth_failed"
    if state == "42501":
        return "permission_denied"
    if state == "3D000":
        return "does_not_exist"
    if state == "53300":
        return "too_many_connections"
    if state == "57P01":
        return "shutdown"
    if state in ("08000", "08001", "08003", "08004", "08006", "08007"):
        return "refused"
    
    return "query_error"


def describe_db_error(exc: BaseException) -> Dict[str, Any]:
    """Формирует детальное описание ошибки PostgreSQL.

    Args:
        exc: Исключение psycopg2 или UnicodeDecodeError

    Returns:
        dict с полями kind, message, detail, hint, sqlstate, severity, user_hint
    """
    if isinstance(exc, UnicodeDecodeError):
        return {
            "kind": "encoding",
            "message": str(exc),
            "detail": None,
            "hint": None,
            "sqlstate": None,
            "severity": None,
            "user_hint": DB_ERROR_HINTS["encoding"],
        }
    
    message = str(exc) or exc.__class__.__name__
    primary = _diag_value(exc, "message_primary")
    if primary and primary not in message:
        message = primary
    
    sqlstate = getattr(exc, "pgcode", None) or _diag_value(exc, "code")
    kind = classify_db_error(sqlstate, message)
    
    return {
        "kind": kind,
        "message": message,
        "detail": _diag_value(exc, "message_detail"),
        "hint": _diag_value(exc, "hint"),
        "sqlstate": sqlstate,
        "severity": _diag_value(exc, "severity"),
        "user_hint": DB_ERROR_HINTS.get(kind, DB_ERROR_HINTS["unknown"]),
    }


def sanitize_db_message(message: str) -> str:
    """Убирает из сообщения адрес и имя пользователя БД.

    Используется для неавторизованных ответов (/health), чтобы не раскрывать
    параметры подключения локальным процессам без ключа.

    Args:
        message: Текст ошибки

    Returns:
        Текст с заменёнными хостом и пользователем
    """
    if not message:
        return message
    
    sanitized = re.sub(r'at "([^"]+)"(?:\s*\(([^)]+)\))?', r'at "<host>"', message)
    sanitized = re.sub(r'user "([^"]+)"', 'user "<user>"', sanitized)
    sanitized = re.sub(r'host=([^\s,]+)', 'host=<host>', sanitized)
    return sanitized.strip()


def parse_dsn(dsn: str) -> dict:
    """Парсит DSN строку в формате postgres://user:pass@host:port/database.

    Args:
        dsn: DSN строка в формате postgres://user:pass@host:port/database
    
    Returns:
        dict с параметрами подключения
    """
    # Поддерживаемые форматы:
    # postgres://user:pass@host:port/db
    # postgresql://user:pass@host:port/db
    # user=xxx password=xxx host=xxx port=xxx dbname=xxx
    
    result: Dict[str, Any] = {}
    dsn = dsn.strip()
    
    # URI формат
    uri_match = re.match(
        r'^(?:postgres|postgresql)://(?:(?P<user>[^:@]+)(?::(?P<password>[^@]*))?@)?(?:(?P<host>[^:/]+)(?::(?P<port>\d+))?)(?:/(?P<database>.*))?$',
        dsn
    )
    
    if uri_match:
        groups = uri_match.groupdict()
        result["host"] = groups.get("host", "localhost") or "localhost"
        result["port"] = int(groups.get("port", 5432)) if groups.get("port") else 5432
        result["database"] = groups.get("database", "") or "postgres"
        result["user"] = groups.get("user", "postgres") or "postgres"
        result["password"] = groups.get("password", "") or ""
        return result
    
    # key=value формат
    kv_match = re.match(
        r'^(?:.*\s+)?user=(?P<user>[^\s]+)(?:\s+password=(?P<password>[^\s]+))?(?:\s+host=(?P<host>[^\s]+))?(?:\s+port=(?P<port>\d+))?(?:\s+dbname=(?P<database>[^\s]+))?',
        dsn
    )
    
    if kv_match:
        groups = kv_match.groupdict()
        result["host"] = groups.get("host", "localhost") or "localhost"
        result["port"] = int(groups.get("port", 5432)) if groups.get("port") else 5432
        result["database"] = groups.get("database", "") or "postgres"
        result["user"] = groups.get("user", "postgres") or "postgres"
        result["password"] = groups.get("password", "") or ""
        return result
    
    raise ValueError(f"Invalid DSN format: {dsn}")


class Database:
    """PostgreSQL database connection manager."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection = None
        self.last_error: Optional[Dict[str, Any]] = None
        self.last_error_at: Optional[datetime] = None
        self._error_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._tables_cache: Optional[List[str]] = None
        self._tables_cache_at: float = 0.0
        self._last_connect_attempt: Optional[float] = None
        self._connect_failed = False
        self._connect()

    def connect_from_dsn(self, dsn_string: str) -> bool:
        """Подключение к БД используя DSN строку.

        Args:
            dsn_string: DSN строка в формате 
                       postgres://user:pass@host:port/database
       
        Returns:
            bool: True если подключение успешно
        """
        try:
            parsed = parse_dsn(dsn_string)
            self.config = parsed
            self._connect()
            return self.is_connected()
        except Exception as e:
            logger.error(f"Failed to connect using DSN: {e}")
            return False

    # ------------------------------------------------------------------
    # Подключение
    # ------------------------------------------------------------------

    def _connect(self):
        """Establish database connection."""
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 5432)
        database = self.config.get("database", "mydb")
        user = self.config.get("user", "postgres")
        
        logger.info(f"Connecting to PostgreSQL: {host}:{port}/{database} as {user}")
        self._last_connect_attempt = time.monotonic()
        
        try:
            self.connection = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=self.config.get("password", ""),
                connect_timeout=CONNECT_TIMEOUT,
                application_name=APPLICATION_NAME,
                cursor_factory=RealDictCursor
            )
            self._connect_failed = False
            self._clear_error()
            logger.info("Database connection established")
        except UnicodeDecodeError as e:
            # This can happen on Windows with non-UTF8 locale (e.g., Russian_Russia.1251)
            error = describe_db_error(e)
            self._record_error(error)
            self._connect_failed = True
            logger.error(f"Database connection failed [{error['kind']}]: {error['message']} "
                         f"— {error['user_hint']}")
            logger.error("This may be caused by encoding mismatch. "
                         "Try setting PGCLIENTENCODING=UTF8 environment variable.")
            logger.debug(f"Connection error details: {error}")
            self.connection = None
        except psycopg2.Error as e:
            error = describe_db_error(e)
            self._record_error(error)
            self._connect_failed = True
            logger.error(f"Database connection failed [{error['kind']}]: {error['message']} "
                         f"— {error['user_hint']}")
            logger.debug(f"Connection error details: {error}")
            self.connection = None

    def should_retry_connect(self, cooldown: float = RECONNECT_COOLDOWN) -> bool:
        """Стоит ли повторно пытаться подключиться.

        После неудачной попытки даётся пауза (RECONNECT_COOLDOWN), иначе каждый
        запрос к недоступной БД тратил бы время на повторное подключение.

        Args:
            cooldown: Пауза между попытками в секундах

        Returns:
            bool: True если можно пробовать подключиться снова
        """
        if not self._connect_failed:
            return True
        
        if self._last_connect_attempt is None:
            return True
        
        return (time.monotonic() - self._last_connect_attempt) >= cooldown

    def is_connected(self) -> bool:
        """Проверяет наличие живого соединения (без round-trip до сервера).

        Returns:
            bool: True если соединение открыто
        """
        if self.connection is None:
            return False
        
        try:
            return not self.connection.closed
        except Exception:
            return False

    def reconnect(self):
        """Reconnect to database."""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
        self._invalidate_tables_cache()
        self._connect()

    # ------------------------------------------------------------------
    # Ошибки
    # ------------------------------------------------------------------

    def _record_error(self, error: Dict[str, Any]):
        """Сохраняет последнюю ошибку для показа в GUI/API."""
        with self._error_lock:
            self.last_error = error
            self.last_error_at = datetime.now()
    
    def _clear_error(self):
        """Сбрасывает последнюю ошибку (после успешного коннекта)."""
        with self._error_lock:
            self.last_error = None
            self.last_error_at = None
    
    @property
    def last_error_message(self) -> Optional[str]:
        """Краткое описание последней ошибки: '<сообщение> — <подсказка>'."""
        with self._error_lock:
            error = self.last_error
        
        if not error:
            return None
        
        message = error.get("message") or "Unknown error"
        hint = error.get("user_hint")
        return f"{message} — {hint}" if hint else message

    def get_last_error(self) -> Optional[Dict[str, Any]]:
        """Возвращает копию последней ошибки."""
        with self._error_lock:
            return dict(self.last_error) if self.last_error else None

    # ------------------------------------------------------------------
    # Выполнение запросов
    # ------------------------------------------------------------------

    def _run(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict]]:
        """Выполняет запрос, при обрыве соединения переподключается и повторяет один раз.

        Args:
            query: SQL-запрос
            params: Параметры запроса

        Returns:
            Список строк (пустой список, если запрос не возвращает результат)
            или None при ошибке
        """
        for attempt in (1, 2):
            if self.connection is None:
                if not self.should_retry_connect():
                    logger.warning("Skipping query: last connection attempt failed recently")
                    return None
                self.reconnect()
            
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    
                    if cursor.description is not None:
                        result = cursor.fetchall()
                    else:
                        result = []
                    
                    self.connection.commit()
                    return result
            except psycopg2.OperationalError as e:
                # Обрыв соединения — переподключаемся и пробуем ещё раз
                error = describe_db_error(e)
                self._record_error(error)
                
                if attempt == 2:
                    logger.error(f"Database query failed [{error['kind']}]: {error['message']} "
                                 f"— {error['user_hint']}")
                    logger.debug(f"Query error details: {error}")
                    self._rollback()
                    return None
                
                logger.warning(f"Connection lost ({error['kind']}), reconnecting and retrying")
                self.reconnect()
            except psycopg2.Error as e:
                error = describe_db_error(e)
                self._record_error(error)
                logger.error(f"Database query failed [{error['kind']}]: {error['message']} "
                             f"— {error['user_hint']}")
                logger.debug(f"Query error details: {error}")
                self._rollback()
                return None
            except Exception as e:
                logger.error(f"Unexpected database error: {type(e).__name__}: {e}")
                self._rollback()
                return None
        
        return None

    def _rollback(self):
        """Откатывает текущую транзакцию (ошибки не должны оставлять транзакцию открытой)."""
        try:
            if self.connection:
                self.connection.rollback()
        except Exception:
            pass

    def execute_query(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict]]:
        """Execute SQL query and return results.

        Для INSERT/UPDATE/DELETE выполняется commit, результат берётся из RETURNING
        (если запрос его не содержит — возвращается пустой список).

        Args:
            query: SQL-запрос
            params: Параметры запроса

        Returns:
            List[Dict] с результатом или None при ошибке
        """
        result = self._run(query, params)
        
        if result is None:
            return None
        
        return result

    def execute_update(self, query: str, params: Optional[tuple] = None) -> bool:
        """Execute INSERT/UPDATE/DELETE query.

        Args:
            query: SQL-запрос
            params: Параметры запроса

        Returns:
            bool: True если запрос выполнен успешно
        """
        return self._run(query, params) is not None

    def execute_batch(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict]]:
        """Execute batch INSERT query with single transaction.
        
        Uses multi-row INSERT syntax for efficiency.
        All inserts are done in a single transaction - either all succeed or all fail.
        
        Args:
            query: Multi-row INSERT query with multiple VALUES groups
            params: Flat tuple of all values (interleaved by row)
            
        Returns:
            List[Dict] with RETURNING data or None on failure
        """
        if params:
            logger.debug(f"Executing batch: {query[:200]}... with {len(params)} params")
        
        return self._run(query, params)

    # ------------------------------------------------------------------
    # Структура БД
    # ------------------------------------------------------------------

    def get_tables(self, max_age: float = 30.0) -> List[str]:
        """Get list of all tables in database (с кэшем на max_age секунд).

        Args:
            max_age: Время жизни кэша в секундах

        Returns:
            List[str] с именами таблиц
        """
        now = time.monotonic()
        
        with self._cache_lock:
            if self._tables_cache is not None and (now - self._tables_cache_at) < max_age:
                return list(self._tables_cache)
        
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        result = self.execute_query(query)
        
        if not result:
            return []
        
        tables = [row["table_name"] for row in result]
        
        with self._cache_lock:
            self._tables_cache = tables
            self._tables_cache_at = time.monotonic()
        
        return list(tables)

    def table_exists(self, table_name: str) -> bool:
        """Проверяет существование таблицы (без полного скана information_schema).

        Args:
            table_name: Имя таблицы

        Returns:
            bool: True если таблица существует
        """
        result = self.execute_query(
            "SELECT to_regclass(%s) IS NOT NULL AS exists",
            (f"public.{table_name}",)
        )
        
        if not result:
            return False
        
        return bool(result[0].get("exists"))
    
    def get_table_columns(self, table_name: str) -> List[Dict]:
        """Get columns for specified table.

        Args:
            table_name: Имя таблицы

        Returns:
            List[Dict] с информацией о колонках
        """
        query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position
        """
        result = self.execute_query(query, (table_name,))
        return result if result else []

    def _invalidate_tables_cache(self):
        """Сбрасывает кэш списка таблиц."""
        with self._cache_lock:
            self._tables_cache = None
            self._tables_cache_at = 0.0

    def close(self, reason: str = ""):
        """Close database connection.

        Args:
            reason: Причина закрытия (для лога)
        """
        self._invalidate_tables_cache()
        if self.connection:
            try:
                self.connection.close()
                suffix = f" ({reason})" if reason else ""
                logger.info(f"Database connection closed{suffix}")
            except Exception as e:
                logger.debug(f"Error while closing connection: {e}")
