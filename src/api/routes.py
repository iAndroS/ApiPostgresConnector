"""API routes for ApiPostgresConnector."""
import logging
import re
from functools import wraps

from flask import Blueprint, g, jsonify, request

from .connections import ConnectionRegistry
from .database import sanitize_db_message
from ..version import APP_VERSION

logger = logging.getLogger(__name__)

# Create API blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# Registry of named connections (each has its own database and API keys)
_registry: ConnectionRegistry = None

# Callback function for updating tray status (last activity time)
_activity_callback = None

# Direct reference to GUI for fallback (set from app.py after GUI is created)
_gui_reference = None


def init_routes(connection_registry: ConnectionRegistry, activity_callback: callable = None,
                gui_reference: object = None):
    """Initialize routes with the connection registry.

    Args:
        connection_registry: Реестр именованных подключений
        activity_callback: Callback function to call on API activity (optional)
        gui_reference: Direct reference to GUI for fallback updates (optional)
    """
    global _registry, _activity_callback, _gui_reference
    
    _registry = connection_registry
    
    if activity_callback is not None:
        _activity_callback = activity_callback
    if gui_reference is not None:
        _gui_reference = gui_reference


def get_registry() -> ConnectionRegistry:
    """Возвращает реестр подключений (или None, если маршруты не инициализированы)."""
    return _registry


# ----------------------------------------------------------------------
# Аутентификация
# ----------------------------------------------------------------------

def _check_api_key(profile) -> tuple:
    """Проверяет заголовок X-API-Key для подключения.

    Args:
        profile: Профиль подключения

    Returns:
        tuple (ok, error_message)
    """
    if profile is None:
        return False, "Database not initialized"
    
    # Аутентификация может быть отключена в настройках (тестовый режим)
    if _registry is not None and not _registry.require_auth:
        return True, ""
    
    # Если у подключения нет ключей — аутентификация не требуется
    if not profile.api_keys:
        return True, ""
    
    key = request.headers.get("X-API-Key")
    
    if not key:
        return False, "Missing API key. Provide X-API-Key header"
    
    if key not in profile.api_keys:
        return False, f'Invalid API key for connection "{profile.name}"'
    
    return True, ""


def require_api_key(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        profile = g.get("connection") or (_registry.get_default() if _registry else None)
        ok, error = _check_api_key(profile)
        if not ok:
            return jsonify({"error": error}), 401
        return f(*args, **kwargs)
    return decorated


def validate_identifier(name: str) -> bool:
    """Валидирует идентификатор SQL (таблица, колонка).

    Args:
        name: Имя идентификатора
        
    Returns:
        bool: True если валидный идентификатор
    """
    if not name:
        return False
    # Проверяем что имя начинается с буквы или _, содержит только буквы, цифры и _
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))


def _resolve_connection():
    """Определяет подключение для текущего запроса.

    Returns:
        ConnectionProfile или None
    """
    if not _registry:
        return None
    
    name = (request.view_args or {}).get("connection_name")
    
    if name:
        return _registry.get(name)
    
    return _registry.get_default()


def _is_public_endpoint() -> bool:
    """True для эндпоинтов без аутентификации (/health, /info без имени подключения)."""
    if (request.view_args or {}).get("connection_name"):
        return False
    return request.endpoint in ('api.health_check', 'api.api_info')


def _ensure_db_connection(profile) -> bool:
    """Ensure database connection is active, reconnect if needed.

    Args:
        profile: Профиль подключения

    Returns:
        bool: True если connected, False otherwise
    """
    if profile is None:
        return False
    
    db = profile.db
    
    # Check if connected
    if not db.is_connected():
        # Недавно была неудачная попытка — не тратим время на новую
        if not db.should_retry_connect():
            logger.warning(
                f"Database for connection '{profile.name}' is unavailable "
                f"(previous attempt failed recently), skipping reconnect")
            return False
        
        logger.warning(f"Database connection lost for connection '{profile.name}', attempting to reconnect...")
        db.reconnect()
        
        if not db.is_connected():
            error = profile.last_error or {}
            details = ""
            if error.get("message"):
                details = f": {error['message']}"
            if error.get("user_hint"):
                details += f" — {error['user_hint']}"
            logger.error(f"Failed to reconnect to database for connection "
                         f"'{profile.name}'{details}")
            return False
        
        logger.info(f"Database reconnected successfully for connection '{profile.name}'")
    
    return True


def _notify_activity():
    """Notify about API activity (update last activity time)."""
    global _activity_callback, _gui_reference
    
    # Try callback first
    if _activity_callback:
        try:
            _activity_callback()
            return
        except Exception as e:
            logger.debug(f"Activity callback error: {e}")
    
    # Fallback: try direct GUI reference
    if _gui_reference:
        try:
            _gui_reference.after(0, _gui_reference.update_tray_status)
        except Exception as e:
            logger.debug(f"Direct GUI update error: {e}")


def _error_payload(profile) -> dict:
    """Формирует описание последней ошибки БД для ответа API."""
    if profile is None:
        return {}
    
    error = profile.last_error
    if not error:
        return {}
    
    return {
        "kind": error.get("kind"),
        "message": error.get("message"),
        "detail": error.get("detail"),
        "hint": error.get("hint"),
        "sqlstate": error.get("sqlstate"),
        "user_hint": error.get("user_hint"),
    }


# Log all incoming requests
@api_bp.before_request
def log_request_info():
    """Log incoming request information with masked sensitive headers."""
    logger.debug(f"Request: {request.method} {request.path} from {request.remote_addr}")
    
    # Log headers with masking sensitive data
    safe_headers = {}
    for key, value in request.headers:
        if key.lower() == 'x-api-key':
            # Mask API key - show only first 3 and last 3 characters
            if len(value) > 6:
                safe_headers[key] = f"{value[:3]}...{value[-3:]}"
            else:
                safe_headers[key] = "***"
        else:
            safe_headers[key] = value
    
    logger.debug(f"Headers: {safe_headers}")


@api_bp.before_request
def check_auth_and_connection():
    """Resolve connection, check authentication and database connection."""
    if not _registry:
        return jsonify({"error": "API not initialized"}), 500
    
    name = (request.view_args or {}).get("connection_name")
    profile = _resolve_connection()
    
    if profile is None:
        return jsonify({"error": f"Unknown connection: {name}"}), 404
    
    g.connection = profile
    g.connection_name = profile.name
    
    # Публичные эндпоинты не требуют ключ и не блокируют подключением к БД:
    # реальное состояние отдаёт /health, а подключение поднимается в фоне
    if _is_public_endpoint():
        g.db = profile.db if profile.is_db_created else None
        return None
    
    # 1. Аутентификация (раньше проверки БД, чтобы не отдавать состояние БД посторонним)
    ok, error = _check_api_key(profile)
    if not ok:
        return jsonify({"error": error, "connection": profile.name}), 401
    
    # 2. Проверка подключения к БД
    g.db = profile.db
    if not _ensure_db_connection(profile):
        return jsonify({
            "error": "Database connection lost. Please reconnect.",
            "database_connected": False,
            "connection": profile.name,
            "reason": _error_payload(profile)
        }), 503
    
    return None


@api_bp.route("/health", methods=["GET"])
@api_bp.route("/c/<connection_name>/health", methods=["GET"])
def health_check(connection_name=None):
    """Health check endpoint (no auth required for the default connection)."""
    profile = g.get("connection")
    db = g.get("db")
    
    error = profile.last_error if profile else None
    
    payload = {
        "status": "ok",
        "database_connected": db.is_connected() if db else False,
        "connection": profile.name if profile else None
    }
    
    if error:
        payload["last_error"] = {
            "kind": error.get("kind"),
            "message": sanitize_db_message(error.get("message") or "")
        }
    
    return jsonify(payload)


@api_bp.route("/info", methods=["GET"])
@api_bp.route("/c/<connection_name>/info", methods=["GET"])
def api_info(connection_name=None):
    """API information endpoint (no auth required for the default connection)."""
    profile = g.get("connection")
    db = g.get("db")
    
    auth_required = bool(_registry.require_auth and _registry.total_key_count() > 0) if _registry else False
    
    payload = {
        "name": "ApiPostgresConnector API",
        "version": APP_VERSION,
        "description": "REST API for PostgreSQL database access",
        "auth_required": auth_required,
        "api_key_count": _registry.total_key_count() if _registry else 0,
        "database_connected": db.is_connected() if db else False,
        "connection": profile.name if profile else None,
        "endpoints": [
            "/api/v1/health",
            "/api/v1/info",
            "/api/v1/tables",
            "/api/v1/tables/<name>/columns",
            "/api/v1/query",
            "/api/v1/tables/<name>/select",
            "/api/v1/tables/<name>/insert",
            "/api/v1/tables/<name>/batch-insert"
        ],
        "named_endpoints": "/api/v1/c/<connection>/<endpoint>"
    }
    
    error = profile.last_error if profile else None
    if error:
        payload["last_error_kind"] = error.get("kind")
    
    return jsonify(payload)


@api_bp.route("/tables", methods=["GET"])
@api_bp.route("/c/<connection_name>/tables", methods=["GET"])
def get_tables(connection_name=None):
    """Get list of all tables."""
    db = g.get("db")
    if not db:
        return jsonify({"error": "Database not initialized"}), 500

    tables = db.get_tables()
    _notify_activity()
    return jsonify({"connection": g.get("connection_name"), "tables": tables})


@api_bp.route("/tables/<table_name>/columns", methods=["GET"])
@api_bp.route("/c/<connection_name>/tables/<table_name>/columns", methods=["GET"])
def get_table_columns(table_name, connection_name=None):
    """Get columns for specified table."""
    db = g.get("db")
    if not db:
        return jsonify({"error": "Database not initialized"}), 500

    # Validate table name
    if not validate_identifier(table_name):
        return jsonify({"error": "Invalid table name"}), 400

    columns = db.get_table_columns(table_name)
    _notify_activity()
    return jsonify({"connection": g.get("connection_name"), "table": table_name, "columns": columns})


@api_bp.route("/query", methods=["POST"])
@api_bp.route("/c/<connection_name>/query", methods=["POST"])
def execute_query(connection_name=None):
    """Execute custom SQL query."""
    db = g.get("db")
    if not db:
        return jsonify({"error": "Database not initialized"}), 500

    data = request.get_json(silent=True)
    if not data or "query" not in data:
        return jsonify({"error": "Query is required"}), 400

    query = data["query"]

    # Security check: only SELECT queries allowed by default
    if not query.strip().upper().startswith("SELECT"):
        return jsonify({"error": "Only SELECT queries are allowed"}), 403

    result = db.execute_query(query)
    if result is None:
        return jsonify({
            "error": "Query execution failed",
            "connection": g.get("connection_name"),
            "reason": _error_payload(g.get("connection"))
        }), 500

    _notify_activity()
    return jsonify({"connection": g.get("connection_name"), "result": result})


@api_bp.route("/tables/<table_name>/select", methods=["GET"])
@api_bp.route("/c/<connection_name>/tables/<table_name>/select", methods=["GET"])
def select_from_table(table_name, connection_name=None):
    """Select rows from table with optional filters."""
    db = g.get("db")
    if not db:
        return jsonify({"error": "Database not initialized"}), 500

    # Validate table name
    if not validate_identifier(table_name):
        return jsonify({"error": "Invalid table name"}), 400

    # Get query parameters
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Check table exists (prevents SQL injection)
    if not db.table_exists(table_name):
        return jsonify({"error": f"Table '{table_name}' not found"}), 404

    query = f'SELECT * FROM "{table_name}" LIMIT %s OFFSET %s'
    result = db.execute_query(query, (limit, offset))

    if result is None:
        return jsonify({
            "error": "Query execution failed",
            "connection": g.get("connection_name"),
            "reason": _error_payload(g.get("connection"))
        }), 500

    _notify_activity()
    return jsonify({
        "connection": g.get("connection_name"),
        "table": table_name,
        "data": result,
        "limit": limit,
        "offset": offset
    })


@api_bp.route("/tables/<table_name>/insert", methods=["POST"])
@api_bp.route("/c/<connection_name>/tables/<table_name>/insert", methods=["POST"])
def insert_into_table(table_name, connection_name=None):
    """Insert row into table."""
    db = g.get("db")
    if not db:
        return jsonify({"error": "Database not initialized"}), 500

    # Validate table name
    if not validate_identifier(table_name):
        return jsonify({"error": "Invalid table name"}), 400

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Data is required (JSON object)"}), 400

    # Check table exists
    if not db.table_exists(table_name):
        return jsonify({"error": f"Table '{table_name}' not found"}), 404

    # Validate column names
    for col in data.keys():
        if not validate_identifier(col):
            return jsonify({"error": f"Invalid column name: {col}"}), 400

    # Build INSERT query
    columns = list(data.keys())
    values = list(data.values())
    placeholders = ", ".join(["%s"] * len(columns))
    column_names = ", ".join([f'"{col}"' for col in columns])

    query = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders}) RETURNING *'

    result = db.execute_query(query, tuple(values))
    if result is None:
        return jsonify({
            "error": "Insert failed",
            "connection": g.get("connection_name"),
            "reason": _error_payload(g.get("connection"))
        }), 500

    _notify_activity()
    return jsonify({
        "success": True,
        "connection": g.get("connection_name"),
        "data": result[0] if result else None
    }), 201


@api_bp.route("/tables/<table_name>/batch-insert", methods=["POST"])
@api_bp.route("/c/<connection_name>/tables/<table_name>/batch-insert", methods=["POST"])
def batch_insert_into_table(table_name, connection_name=None):
    """Batch insert multiple rows into table.
    
    Expects JSON array of objects:
    [
        {"column1": "value1", "column2": "value2"},
        {"column1": "value3", "column2": "value4"}
    ]
    
    Uses single multi-row INSERT statement with transaction for efficiency.
    """
    db = g.get("db")
    if not db:
        return jsonify({"error": "Database not initialized"}), 500

    # Validate table name
    if not validate_identifier(table_name):
        return jsonify({"error": "Invalid table name"}), 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Data is required"}), 400

    # Check if data is a list
    if not isinstance(data, list):
        return jsonify({"error": "Expected JSON array of objects"}), 400

    if len(data) == 0:
        return jsonify({"error": "Array cannot be empty"}), 400

    # Get columns from first row
    first_row = data[0]
    if not isinstance(first_row, dict):
        return jsonify({"error": "Each item must be an object"}), 400

    columns = list(first_row.keys())

    # Limit batch size to prevent memory exhaustion
    MAX_BATCH_SIZE = 1000
    if len(data) > MAX_BATCH_SIZE:
        return jsonify({"error": f"Batch size exceeds maximum of {MAX_BATCH_SIZE} rows"}), 400
    
    # Все строки должны содержать одинаковый набор колонок, иначе данные теряются молча
    for index, row in enumerate(data):
        if not isinstance(row, dict):
            return jsonify({"error": f"Row must be object, got {type(row).__name__}", "row": index}), 400
        if set(row.keys()) != set(columns):
            missing = sorted(set(columns) - set(row.keys()))
            extra = sorted(set(row.keys()) - set(columns))
            return jsonify({
                "error": f"Row {index} has different columns",
                "missing": missing,
                "unexpected": extra
            }), 400
    
    # Validate column names
    for col in columns:
        if not validate_identifier(col):
            return jsonify({"error": f"Invalid column name: {col}"}), 400

    # Check table exists
    if not db.table_exists(table_name):
        # Try to create table based on first row
        # Build CREATE TABLE statement
        column_defs = []
        for col in columns:
            column_defs.append(f'"{col}" TEXT')
        
        # Add timestamp column for auto-recording parse time
        column_defs.append('"parsed_at" TIMESTAMP DEFAULT NOW()')
        
        create_query = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(column_defs)})'
        logger.info(f"Creating table '{table_name}' with columns: {columns}")
        
        if not db.execute_update(create_query):
            return jsonify({"error": f"Failed to create table '{table_name}'"}), 500
        
        if not db.table_exists(table_name):
            return jsonify({"error": f"Failed to create table '{table_name}'"}), 500
        
        logger.info(f"Table '{table_name}' created successfully")
    
    # Build multi-row INSERT query
    # Using single INSERT with multiple VALUES groups for better performance
    placeholders = ", ".join(["%s"] * len(columns))
    column_names = ", ".join([f'"{col}"' for col in columns])
    
    values_placeholder = ", ".join([f"({placeholders})"] * len(data))
    query = f'INSERT INTO "{table_name}" ({column_names}) VALUES {values_placeholder} RETURNING *'
    
    # Try to convert string numbers to actual numbers
    def convert_value(val):
        """Convert string numbers to int/float, leave other values as-is."""
        if isinstance(val, str):
            # Try integer
            try:
                return int(val)
            except ValueError:
                pass
            # Try float
            try:
                return float(val)
            except ValueError:
                pass
            # Check for boolean strings
            if val.lower() == 'true':
                return True
            if val.lower() == 'false':
                return False
        return val

    # Flatten all values into a single tuple
    all_values = []
    for row in data:
        row_values = []
        for col in columns:
            # Convert values - strings like "123" become numbers
            row_values.append(convert_value(row.get(col)))
        all_values.extend(row_values)
    
    # Execute as single query with transaction
    try:
        result = db.execute_batch(query, tuple(all_values))
    except Exception as e:
        logger.error(f"Batch insert error: {e}")
        return jsonify({"error": f"Batch insert failed: {str(e)}"}), 500
    
    _notify_activity()
    
    if result is None:
        return jsonify({
            "error": "Batch insert failed - check server logs for details",
            "connection": g.get("connection_name"),
            "reason": _error_payload(g.get("connection"))
        }), 500
    
    return jsonify({
        "success": True,
        "connection": g.get("connection_name"),
        "inserted": len(result),
        "data": result
    }), 201
