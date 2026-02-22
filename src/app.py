"""ApiPostgresConnector - Main application entry point."""
import logging
import secrets
import sys
import threading
from pathlib import Path
import os

# Add paths for both development and pyinstaller
_base_path = Path(__file__).parent
sys.path.insert(0, str(_base_path))

# For pyinstaller: add _internal to path to find config
if getattr(sys, 'frozen', False):
    sys.path.insert(0, str(sys._MEIPASS))

from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

from src.config import config
from src.api.database import Database
from src.api.routes import api_bp, init_routes
from src.gui.main_window import MainWindow


# Configure logging
# Determine log file path - use app directory
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    log_dir = Path(sys._MEIPASS).parent
else:
    # Running in development
    log_dir = Path(__file__).parent.parent

log_file = log_dir / "app.log"

# Check if file logging is enabled in config
enable_logging = config.app.get("enable_logging", True)

# Configure logging with optional file handler
handlers = [logging.StreamHandler(sys.stdout)]
if enable_logging:
    handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers
)
logger = logging.getLogger(__name__)
logger.info(f"Log file: {log_file} (file logging: {enable_logging})")


class APIServer:
    """Flask API server manager."""

    def __init__(self):
        self.app = None
        self.server_thread = None
        self._running = False

    def _create_app(self, host: str, port: int) -> Flask:
        """Create and configure Flask application."""
        app = Flask(__name__)
        CORS(app)

        # Initialize database
        db = Database(config.database)

        # Initialize routes with API keys
        api_keys = set(config.api.get("api_keys", []))
        init_routes(db, api_keys)

        # Register blueprint
        app.register_blueprint(api_bp)

        # API documentation page
        @app.route("/")
        def index():
            """API documentation page."""
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>ApiPostgresConnector API</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        max-width: 800px;
                        margin: 50px auto;
                        padding: 20px;
                        background: #1a1a1a;
                        color: #ffffff;
                    }
                    h1 { color: #4a9eff; }
                    h2 { color: #7cb3ff; margin-top: 30px; }
                    .endpoint {
                        background: #2d2d2d;
                        padding: 15px;
                        margin: 10px 0;
                        border-radius: 5px;
                        border-left: 4px solid #4a9eff;
                    }
                    .method {
                        display: inline-block;
                        padding: 3px 8px;
                        border-radius: 3px;
                        font-weight: bold;
                        margin-right: 10px;
                    }
                    .get { background: #28a745; color: white; }
                    .post { background: #007bff; color: white; }
                    code {
                        background: #3d3d3d;
                        padding: 2px 6px;
                        border-radius: 3px;
                    }
                    a { color: #4a9eff; }
                </style>
            </head>
            <body>
                <h1>🚀 ApiPostgresConnector API</h1>
                <p>REST API для подключения к PostgreSQL</p>

                <h2>📋 Доступные эндпоинты</h2>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <code>/api/v1/health</code>
                    <p>Проверка состояния API и подключения к БД</p>
                </div>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <code>/api/v1/tables</code>
                    <p>Получить список всех таблиц в базе данных</p>
                </div>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <code>/api/v1/tables/<table_name>/columns</code>
                    <p>Получить колонки указанной таблицы</p>
                </div>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <code>/api/v1/tables/<table_name>/select?limit=100&offset=0</code>
                    <p>Выбрать данные из таблицы</p>
                </div>

                <div class="endpoint">
                    <span class="method post">POST</span>
                    <code>/api/v1/tables/<table_name>/insert</code>
                    <p>Вставить данные в таблицу (JSON в теле запроса)</p>
                </div>

                <div class="endpoint">
                    <span class="method post">POST</span>
                    <code>/api/v1/query</code>
                    <p>Выполнить произвольный SQL запрос (только SELECT)</p>
                </div>

                <h2>📖 Примеры использования</h2>

                <h3>C# (ZennoPoster)</h3>
                <pre><code>// Получить список таблиц
var tables = instance.ActiveTab.Document.GetTag("DIV")
    .Post("http://127.0.0.1:5000/api/v1/tables", "")
    .ToString();</code></pre>

                <h3>Python</h3>
                <pre><code>import requests

# Проверка здоровья API
response = requests.get("http://127.0.0.1:5000/api/v1/health")
print(response.json())

# Получить таблицы
tables = requests.get("http://127.0.0.1:5000/api/v1/tables").json()</code></pre>

                <footer>
                    <p><small>ApiPostgresConnector v1.0.0</small></p>
                </footer>
            </body>
            </html>
            """
            return render_template_string(html)

        return app

    def start(self, host: str = None, port: int = None):
        """Start the API server."""
        if self._running:
            logger.warning("API server is already running")
            return

        # Use config values if not provided
        if host is None:
            host = config.api.get("host", "127.0.0.1")
        if port is None:
            port = config.api.get("port", 5000)

        # Auto-generate API key if none exists
        api_keys = config.api.get("api_keys", [])
        if not api_keys:
            new_key = secrets.token_urlsafe(32)
            logger.info(f"No API key found. Generating new key: {new_key[:8]}...")
            config.update_api(api_keys=[new_key])
            config.save()
            logger.info("API key saved to config")

        self.app = self._create_app(host, port)

        # Get debug mode from config
        debug_mode = config.api.get("debug", False)

        def run_server():
            self.app.run(host=host, port=port, threaded=True, use_reloader=False, debug=debug_mode)

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self._running = True

        logger.info(f"API server started on {host}:{port} (debug={debug_mode})")

    def stop(self):
        """Stop the API server."""
        if not self._running:
            return

        # Note: Flask's run() doesn't support clean shutdown in this setup
        # The daemon thread will be terminated when main app exits
        self._running = False
        logger.info("API server stopped")

    def is_running(self) -> bool:
        """Check if API server is running."""
        return self._running


def main():
    """Main application entry point."""
    logger.info("Starting ApiPostgresConnector...")

    # Create API server instance
    api_server = APIServer()

    # Auto-start API if configured
    if config.app.get("auto_start_api", True):
        api_server.start()
        logger.info("API server auto-started")

    # Create and run GUI
    gui = MainWindow(api_server=api_server)
    gui.run()

    # Cleanup
    api_server.stop()
    logger.info("ApiPostgresConnector closed")


if __name__ == "__main__":
    main()
