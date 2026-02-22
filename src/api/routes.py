"""API routes for ApiPostgresConnector."""
import logging
import re
from functools import wraps

from flask import Blueprint, jsonify, request

from .database import Database

logger = logging.getLogger(__name__)

# Create API blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# Global database instance
db_instance = None

# API Keys set - loaded from config
API_KEYS = set()


def init_routes(database: Database, api_keys: set = None):
    """Initialize routes with database instance.
    
    Args:
        database: Database instance
        api_keys: Set of valid API keys (optional)
    """
    global db_instance, API_KEYS
    db_instance = database
    if api_keys is not None:
        API_KEYS = api_keys


def require_api_key(f):
    """Decorator to require API key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key")
        if not key:
            return jsonify({"error": "Missing API key. Provide X-API-Key header"}), 401
        if key not in API_KEYS:
            return jsonify({"error": "Invalid API key"}), 401
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



@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint (no auth required)."""
    return jsonify({
        "status": "ok",
        "database_connected": db_instance.is_connected() if db_instance else False
    })


@api_bp.route("/info", methods=["GET"])
def api_info():
    """API information endpoint (no auth required)."""
    return jsonify({
        "name": "ApiPostgresConnector API",
        "version": "1.0.0",
        "description": "REST API for PostgreSQL database access",
        "auth_required": len(API_KEYS) > 0,
        "endpoints": [
            "/api/v1/health",
            "/api/v1/tables",
            "/api/v1/tables/<name>/columns",
            "/api/v1/query",
            "/api/v1/tables/<name>/select",
            "/api/v1/tables/<name>/insert"
        ]
    })


# All other routes require API key if configured
@api_bp.before_request
def check_auth():
    """Check authentication before each request."""
    # Skip auth for health and info endpoints
    if request.endpoint in ['api.health_check', 'api.api_info']:
        return None
    
    # If API keys are configured, require authentication
    if API_KEYS:
        key = request.headers.get("X-API-Key")
        if not key or key not in API_KEYS:
            return jsonify({"error": "Unauthorized. Valid API key required."}), 401
    
    return None


@api_bp.route("/tables", methods=["GET"])
def get_tables():
    """Get list of all tables."""
    if not db_instance:
        return jsonify({"error": "Database not initialized"}), 500

    tables = db_instance.get_tables()
    return jsonify({"tables": tables})


@api_bp.route("/tables/<table_name>/columns", methods=["GET"])
def get_table_columns(table_name):
    """Get columns for specified table."""
    if not db_instance:
        return jsonify({"error": "Database not initialized"}), 500

    # Validate table name
    if not validate_identifier(table_name):
        return jsonify({"error": "Invalid table name"}), 400

    columns = db_instance.get_table_columns(table_name)
    return jsonify({"table": table_name, "columns": columns})


@api_bp.route("/query", methods=["POST"])
def execute_query():
    """Execute custom SQL query."""
    if not db_instance:
        return jsonify({"error": "Database not initialized"}), 500

    data = request.get_json()
    if not data or "query" not in data:
        return jsonify({"error": "Query is required"}), 400

    query = data["query"]

    # Security check: only SELECT queries allowed by default
    if not query.strip().upper().startswith("SELECT"):
        return jsonify({"error": "Only SELECT queries are allowed"}), 403

    result = db_instance.execute_query(query)
    if result is None:
        return jsonify({"error": "Query execution failed"}), 500

    return jsonify({"result": result})


@api_bp.route("/tables/<table_name>/select", methods=["GET"])
def select_from_table(table_name):
    """Select rows from table with optional filters."""
    if not db_instance:
        return jsonify({"error": "Database not initialized"}), 500

    # Validate table name
    if not validate_identifier(table_name):
        return jsonify({"error": "Invalid table name"}), 400

    # Get query parameters
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Validate table name (prevent SQL injection)
    tables = db_instance.get_tables()
    if table_name not in tables:
        return jsonify({"error": f"Table '{table_name}' not found"}), 404

    query = f'SELECT * FROM "{table_name}" LIMIT %s OFFSET %s'
    result = db_instance.execute_query(query, (limit, offset))

    if result is None:
        return jsonify({"error": "Query execution failed"}), 500

    return jsonify({"table": table_name, "data": result, "limit": limit, "offset": offset})


@api_bp.route("/tables/<table_name>/insert", methods=["POST"])
def insert_into_table(table_name):
    """Insert row into table."""
    if not db_instance:
        return jsonify({"error": "Database not initialized"}), 500

    # Validate table name
    if not validate_identifier(table_name):
        return jsonify({"error": "Invalid table name"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Data is required"}), 400

    # Validate table name
    tables = db_instance.get_tables()
    if table_name not in tables:
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

    result = db_instance.execute_query(query, tuple(values))
    if result is None:
        return jsonify({"error": "Insert failed"}), 500

    return jsonify({"success": True, "data": result[0]}), 201
