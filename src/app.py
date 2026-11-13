"""ApiPostgresConnector - Main application entry point."""
import logging
import socket
import sys
import threading
import time
from pathlib import Path

# Add paths for both development and pyinstaller
_base_path = Path(__file__).parent
sys.path.insert(0, str(_base_path))

# For pyinstaller: add _MEIPASS to path to find config
if getattr(sys, 'frozen', False):
    sys.path.insert(0, str(sys._MEIPASS))

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.serving import make_server

from src.config import config, get_base_dir
from src.api.connections import ConnectionRegistry
from src.api.routes import api_bp, init_routes
from src.gui.main_window import MainWindow
from src.version import APP_NAME, APP_VERSION, VERSION_STRING


# Configure logging
# Determine log file path - use app directory (next to EXE when frozen)
log_dir = get_base_dir()

log_file = log_dir / "app.log"

# Check if file logging is enabled in config
enable_logging = config.app.get("enable_logging", True)

# Configure logging with optional file handler
handlers = []

# Консоль: принудительно UTF-8, иначе кириллица в терминале Windows
# превращается в мусор (консоль по умолчанию CP866/CP1251)
if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    handlers.append(logging.StreamHandler(sys.stdout))

if enable_logging:
    try:
        # utf-8-sig — чтобы Блокнот и старые редакторы не ломали кириллицу
        handlers.append(logging.FileHandler(log_file, encoding="utf-8-sig"))
    except OSError as e:
        print(f"File logging disabled: {e}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers
)
logger = logging.getLogger(__name__)
logger.info(f"Log file: {log_file} (file logging: {enable_logging})")

# Origins allowed for browser requests (API работает на localhost)
LOCAL_ORIGINS = ["http://127.0.0.1:*", "http://localhost:*"]

API_DOCS_HTML = """
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
        pre {
            background: #2d2d2d;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }
        .note { color: #ffb347; }
        a { color: #4a9eff; }
    </style>
</head>
<body>
    <h1>🚀 ApiPostgresConnector API</h1>
    <p>REST API для подключения к PostgreSQL</p>

    <p class="note">
        Имя подключения указывается в URL после <code>/c/</code>. Все эндпоинты кроме
        <code>health</code> и <code>info</code> требуют заголовок <code>X-API-Key</code>
        именно этого подключения. Браузер отправить такой заголовок не может —
        используйте curl, Postman или Python.
    </p>

    <h2>📋 Доступные эндпоинты</h2>

    <div class="endpoint">
        <span class="method get">GET</span>
        <code>/api/v1/c/&lt;имя_подключения&gt;/health</code>
        <p>Проверка состояния API и подключения к БД</p>
    </div>

    <div class="endpoint">
        <span class="method get">GET</span>
        <code>/api/v1/c/&lt;имя_подключения&gt;/info</code>
        <p>Информация об API (auth_required, количество ключей)</p>
    </div>

    <div class="endpoint">
        <span class="method get">GET</span>
        <code>/api/v1/c/&lt;имя_подключения&gt;/tables</code>
        <p>Список всех таблиц в подключении</p>
    </div>

    <div class="endpoint">
        <span class="method get">GET</span>
        <code>/api/v1/c/&lt;имя_подключения&gt;/tables/&lt;table_name&gt;/columns</code>
        <p>Колонки указанной таблицы</p>
    </div>

    <div class="endpoint">
        <span class="method get">GET</span>
        <code>/api/v1/c/&lt;имя_подключения&gt;/tables/&lt;table_name&gt;/select?limit=100&amp;offset=0</code>
        <p>Выбрать данные из таблицы</p>
    </div>

    <div class="endpoint">
        <span class="method post">POST</span>
        <code>/api/v1/c/&lt;имя_подключения&gt;/tables/&lt;table_name&gt;/insert</code>
        <p>Вставить одну запись в таблицу (JSON объект в теле запроса)</p>
    </div>

    <div class="endpoint">
        <span class="method post">POST</span>
        <code>/api/v1/c/&lt;имя_подключения&gt;/tables/&lt;table_name&gt;/batch-insert</code>
        <p>Массовая вставка записей (JSON массив объектов, максимум 1000)</p>
    </div>

    <div class="endpoint">
        <span class="method post">POST</span>
        <code>/api/v1/c/&lt;имя_подключения&gt;/query</code>
        <p>Выполнить произвольный SQL запрос (только SELECT)</p>
    </div>

    <h2>🔀 Несколько подключений</h2>

    <p>
        У каждого подключения своя база данных и свой API-ключ. Имя подключения
        указывается в URL после <code>/c/</code>:
    </p>

    <pre><code>GET /api/v1/c/&lt;имя_подключения&gt;/tables
GET /api/v1/c/&lt;имя_подключения&gt;/tables/&lt;table_name&gt;/select
POST /api/v1/c/&lt;имя_подключения&gt;/query</code></pre>

    <p>Ключ подключения работает только со своим подключением.</p>

    <h2>📖 Примеры использования</h2>

    <h3>curl</h3>
    <pre><code># Список таблиц подключения crm
curl -H "X-API-Key: your-api-key" http://127.0.0.1:5000/api/v1/c/crm/tables

# SELECT
curl -H "X-API-Key: your-api-key" \
     "http://127.0.0.1:5000/api/v1/c/crm/tables/users/select?limit=10"</code></pre>

    <h3>Python</h3>
    <pre><code>import requests

BASE = "http://127.0.0.1:5000/api/v1"
HEADERS = {"X-API-Key": "your-api-key"}

# Проверка здоровья API (без ключа)
print(requests.get(f"{BASE}/c/crm/health").json())

# Таблицы подключения
tables = requests.get(f"{BASE}/c/crm/tables", headers=HEADERS).json()</code></pre>

    <h3>PowerShell</h3>
    <pre><code>Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/v1/c/crm/tables" `
    -Headers @{ "X-API-Key" = "your-api-key" }</code></pre>

    <footer>
        <p><small>{{VERSION}}</small></p>
    </footer>
</body>
</html>
"""


# Страница-«пробник»: выполняет GET-запрос к API прямо из браузера.
# Заголовок X-API-Key подставляет сервер, поэтому ключ не попадает в URL.
TRY_PAGE_HTML = """
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
            background: #1a1a1a;
            color: #ffffff;
        }
        h1 { color: #4a9eff; font-size: 20px; }
        .field { margin: 12px 0; }
        .field label { display: block; margin-bottom: 4px; color: #b0b0b0; font-size: 13px; }
        input[type="text"], select, textarea {
            width: 100%;
            box-sizing: border-box;
            background: #2d2d2d;
            color: #ffffff;
            border: 1px solid #444444;
            border-radius: 5px;
            padding: 8px 10px;
            font-family: Consolas, monospace;
            font-size: 13px;
        }
        textarea { min-height: 120px; resize: vertical; }
        button {
            background: #4a9eff;
            color: white;
            border: none;
            padding: 10px 18px;
            border-radius: 5px;
            font-size: 14px;
            cursor: pointer;
        }
        button:disabled { background: #555; cursor: default; }
        pre {
            background: #2d2d2d;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            max-height: 55vh;
        }
        .status { margin: 10px 0; color: #7cb3ff; }
        .note { color: #ffb347; font-size: 13px; }
        .row { display: flex; gap: 10px; align-items: flex-end; }
        .row .field.method { width: 130px; flex: 0 0 130px; }
        .row .field.path { flex: 1 1 auto; }
        .examples a { color: #7cb3ff; margin-right: 12px; }
    </style>
</head>
<body>
    <h1>Проверка запроса к API</h1>
    
    <div class="row">
        <div class="field method">
            <label for="method">Метод</label>
            <select id="method">
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="DELETE">DELETE</option>
            </select>
        </div>
        <div class="field path">
            <label for="path">Путь запроса (можно менять)</label>
            <input type="text" id="path" value="{{ path }}" spellcheck="false">
        </div>
    </div>
    
    <div class="field">
        <label for="body">Тело запроса (JSON, для POST — например {"query": "SELECT 1"})</label>
        <textarea id="body" spellcheck="false" placeholder='{"query": "SELECT * FROM table LIMIT 10"}'></textarea>
    </div>
    
    <div class="examples">
        <label>Быстрые примеры:</label><br>
        <a href="#" data-path="/api/v1/c/{connection}/health">health</a>
        <a href="#" data-path="/api/v1/c/{connection}/info">info</a>
        <a href="#" data-path="/api/v1/c/{connection}/tables">tables</a>
        <a href="#" data-path="/api/v1/c/{connection}/tables/users/select?limit=10">select</a>
        <a href="#" data-path="/api/v1/c/{connection}/query">query (POST)</a>
    </div>
    
    <p>
        <button id="send">Выполнить запрос</button>
        <span class="status" id="status"></span>
    </p>
    
    <pre id="result">Нажмите «Выполнить запрос»</pre>
    
    <p class="note">
        Запрос выполняется с сервера приложения: заголовок X-API-Key подставляется автоматически
        по имени подключения из пути, сам ключ в URL не попадает.
    </p>
    
    <script>
        const connection = {{ connection|tojson }};
        const button = document.getElementById('send');
        const status = document.getElementById('status');
        const result = document.getElementById('result');
        const pathInput = document.getElementById('path');
        const methodSelect = document.getElementById('method');
        const bodyInput = document.getElementById('body');
        
        // Подставляем имя подключения в примеры
        document.querySelectorAll('.examples a').forEach(link => {
            link.addEventListener('click', event => {
                event.preventDefault();
                const target = link.getAttribute('data-path').replace('{connection}', connection);
                pathInput.value = target;
                methodSelect.value = target.endsWith('/query') ? 'POST' : 'GET';
                if (methodSelect.value === 'POST') {
                    bodyInput.value = JSON.stringify({query: 'SELECT 1'}, null, 2);
                }
            });
        });
        
        button.addEventListener('click', async () => {
            const path = pathInput.value.trim();
            const method = methodSelect.value;
            const body = bodyInput.value.trim();
            
            if (!path) {
                status.textContent = 'Укажите путь запроса';
                return;
            }
            
            button.disabled = true;
            status.textContent = 'Выполняется...';
            result.textContent = '';
            
            try {
                const payload = {path: path, method: method, body: body};
                const response = await fetch('/try/request', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                
                if (data.error) {
                    status.textContent = 'Ошибка: ' + data.error;
                    result.textContent = '';
                } else {
                    status.textContent = 'HTTP ' + data.status;
                    const content = data.data;
                    result.textContent = (typeof content === 'string')
                        ? content
                        : JSON.stringify(content, null, 2);
                }
            } catch (e) {
                status.textContent = 'Ошибка запроса';
                result.textContent = String(e);
            } finally {
                button.disabled = false;
            }
        });
    </script>
</body>
</html>
"""


def _default_api_path() -> str:
    """Путь API по умолчанию для страницы-«пробника» — health первого подключения."""
    from urllib.parse import quote

    names = config.get_connection_names()
    if not names:
        return "/api/v1/health"

    return f"/api/v1/c/{quote(names[0])}/health"


def _encode_path(path: str) -> str:
    """Кодирует путь запроса для обращения по HTTP (пробелы, кириллица)."""
    from urllib.parse import quote

    return quote(path, safe="/?&=%:+,#~@!$'()*-._")


def _connection_name_for_path(path: str) -> str:
    """Возвращает имя подключения, указанное в пути."""
    import re
    from urllib.parse import unquote

    match = re.match(r"^/api/v1/c/([^/]+)/", path)
    if match:
        return unquote(match.group(1))

    names = config.get_connection_names()
    return names[0] if names else ""


def _api_key_for_path(path: str) -> str:
    """Возвращает API-ключ для подключения, указанного в пути.

    Args:
        path: Путь запроса, например /api/v1/c/crm/tables

    Returns:
        API-ключ подключения (пустая строка, если ключа нет)
    """
    import re
    from urllib.parse import unquote
    
    match = re.match(r"^/api/v1/c/([^/]+)/", path)
    connection = None
    
    if match:
        connection = config.get_connection(unquote(match.group(1)))
    
    if not connection:
        return ""
    
    api_keys = connection.get("api_keys") or []
    return api_keys[0] if api_keys else ""

# Подстановка версии в документацию (в HTML есть фигурные скобки — f-string не подходит)
API_DOCS_HTML = API_DOCS_HTML.replace("{{VERSION}}", VERSION_STRING)


class APIServer:
    """Flask API server manager."""
    def __init__(self, gui_reference=None):
        self.app = None
        self.server = None
        self.server_thread = None
        self.registry = None
        self._running = False
        self._gui_reference = gui_reference

    @staticmethod
    def _is_port_in_use(host: str, port: int, timeout: float = 0.5) -> bool:
        """Проверяет, слушает ли кто-то порт.

        На Windows werkzeug включает SO_REUSEADDR, поэтому второй экземпляр
        приложения может «успешно» занять занятый порт — проверяем заранее.

        Args:
            host: Адрес сервера
            port: Порт
            timeout: Таймаут подключения

        Returns:
            bool: True если порт уже используется
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                return sock.connect_ex((host, port)) == 0
        except OSError:
            return False

    def _create_app(self, host: str, port: int) -> Flask:
        """Create and configure Flask application."""
        app = Flask(__name__)
        CORS(app, resources={r"/api/*": {"origins": LOCAL_ORIGINS}})

        # Логирование запросов: до обработки и после (с кодом ответа и таймингом)
        @app.before_request
        def log_request_start():
            from flask import g, request

            g.request_started_at = time.monotonic()
            length = request.content_length or 0
            logger.info(
                f"-> {request.method} {request.path}"
                f"{(' (' + str(length) + ' B)') if length else ''}"
                f" from {request.remote_addr}"
            )

        @app.after_request
        def log_request_end(response):
            from flask import g, request

            started = getattr(g, "request_started_at", None)
            duration = time.monotonic() - started if started else 0.0
            size = response.calculate_content_length() or 0
            logger.info(
                f"<- {request.method} {request.path} {response.status_code} "
                f"за {duration:.2f}s, {size} B"
            )
            return response

        # JSON-ответы вместо HTML для ошибок Flask
        @app.errorhandler(HTTPException)
        def handle_http_exception(exc):
            return jsonify({"error": exc.description, "status": exc.code}), exc.code

        @app.errorhandler(Exception)
        def handle_unexpected_exception(exc):
            logger.exception(f"Unhandled error: {exc}")
            return jsonify({"error": "Internal server error"}), 500

        # Реестр именованных подключений (БД + свои API-ключи)
        self.registry = ConnectionRegistry(config)
        
        # Подключение к БД в фоне: состояние соединения известно сразу,
        # но запуск приложения и HTTP-запросы не блокируются
        self.registry.start_background_connect()

        # Callback активности: обновляет время последнего запроса в трее.
        # Вызывается из рабочего потока сервера, поэтому не используем
        # Tk-методы (after) — update_tray_status трогает только иконку трея.
        activity_callback = None
        if self._gui_reference:
            def callback():
                try:
                    self._gui_reference.update_tray_status()
                except Exception:
                    pass  # GUI may not be ready
            activity_callback = callback
        
        init_routes(self.registry, activity_callback)

        # Register blueprint
        app.register_blueprint(api_bp)

        # API documentation page
        @app.route("/")
        def index():
            """API documentation page."""
            return render_template_string(API_DOCS_HTML)

        # Страница-«пробник»: выполняет запрос к API из браузера,
        # подставляя заголовок X-API-Key на стороне сервера
        @app.route("/try")
        def try_endpoint():
            """Страница-«пробник»: форма для отправки запросов к API."""
            from flask import request
            from urllib.parse import unquote

            path = unquote(request.args.get("path") or _default_api_path())
            
            if not path.startswith("/api/"):
                path = _default_api_path()
            
            return render_template_string(
                TRY_PAGE_HTML, path=path, connection=_connection_name_for_path(path),
                version=APP_VERSION)
        
        @app.route("/try/request", methods=["POST"])
        def try_request():
            """Выполняет запрос к API от имени сервера.
            
            Ключ подставляется по имени подключения из пути, поэтому в браузере
            ключ не нужен — в том числе при отключённой аутентификации.
            """
            import json as json_module
            import urllib.error
            import urllib.request
            
            from flask import request
            
            data = request.get_json(silent=True) or {}
            path = (data.get("path") or "").strip()
            method = (data.get("method") or "GET").upper()
            body = (data.get("body") or "").strip()
            
            if not path.startswith("/api/"):
                return jsonify({"error": "Путь должен начинаться с /api/"}), 400
            
            host, port = "127.0.0.1", 5000
            if self.server is not None:
                address = self.server.server_address
                host, port = address[0], address[1]
            else:
                host = config.api.get("host", host)
                port = config.api.get("port", port)
            
            headers = {}
            api_key = _api_key_for_path(path)
            if api_key:
                headers["X-API-Key"] = api_key
            
            payload = None
            if body:
                payload = body.encode("utf-8")
                headers["Content-Type"] = "application/json"
            
            request_obj = urllib.request.Request(
                f"http://{host}:{port}{_encode_path(path)}", data=payload, headers=headers,
                method=method)
            
            try:
                with urllib.request.urlopen(request_obj, timeout=30) as response:
                    text = response.read().decode("utf-8", errors="replace")
                    status = response.status
            except urllib.error.HTTPError as e:
                text = e.read().decode("utf-8", errors="replace")
                status = e.code
            except Exception as e:
                return jsonify({"error": str(e)}), 500
            
            try:
                parsed = json_module.loads(text)
            except Exception:
                parsed = None
            
            return jsonify({"status": status, "data": parsed if parsed is not None else text})
        
        return app

    def start(self, host: str = None, port: int = None) -> bool:
        """Start the API server.

        Returns:
            bool: True если сервер запущен, False при ошибке (например, порт занят)
        """
        if self._running:
            logger.warning("API server is already running")
            return True

        # Use config values if not provided
        if host is None:
            host = config.api.get("host", "127.0.0.1")
        if port is None:
            port = config.api.get("port", 5000)

        self.app = self._create_app(host, port)

        # Get debug mode from config
        debug_mode = config.api.get("debug", False)
        self.app.debug = debug_mode

        # Порт уже занят другим процессом (в т.ч. вторым экземпляром приложения)
        if self._is_port_in_use(host, port):
            logger.error(f"Cannot start API server: {host}:{port} is already in use")
            self.app = None
            return False

        # make_server создаёт сокет сразу — ошибка занятости порта видна синхронно
        try:
            self.server = make_server(host, port, self.app, threaded=True)
        except OSError as e:
            logger.error(f"Failed to start API server on {host}:{port}: {e}")
            self.server = None
            self._running = False
            return False

        def run_server():
            self.server.serve_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self._running = True

        logger.info(f"API server started on {host}:{port} (debug={debug_mode})")
        return True

    def stop(self):
        """Stop the API server (полностью освобождает порт)."""
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
                logger.info("API server stopped")
            except Exception as e:
                logger.error(f"Error while stopping API server: {e}")
            finally:
                self.server = None
        
        self.server_thread = None
        self._running = False

    def is_running(self) -> bool:
        """Check if API server is running."""
        return self._running


# Дескриптор мьютекса единственного экземпляра (не даёт мьютексу умереть)
_single_instance_handle = None


def acquire_single_instance() -> bool:
    """Гарантирует, что запущен только один экземпляр приложения.

    На Windows используется именованный мьютекс: второй экземпляр получает
    ERROR_ALREADY_EXISTS и должен завершиться, иначе копии конфликтуют
    за порт API и файл конфигурации.

    Returns:
        bool: True если этот процесс может продолжить работу
    """
    global _single_instance_handle

    if sys.platform != "win32":
        return True

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, "ApiPostgresConnector.SingleInstance")

        if not handle:
            return True

        # ERROR_ALREADY_EXISTS = 183
        if kernel32.GetLastError() == 183:
            kernel32.CloseHandle(handle)
            return False

        _single_instance_handle = handle
        return True
    except Exception as e:
        logger.warning(f"Single-instance check failed: {e}")
        return True


def _show_already_running_message():
    """Показывает сообщение о том, что приложение уже запущено."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(
            "ApiPostgresConnector",
            "Приложение уже запущено.\n\n"
            "Найдите его значок в системном трее — возможно, "
            "он находится в скрытых значках (стрелка ^ рядом с часами).",
        )
        root.destroy()
    except Exception as e:
        logger.warning(f"Failed to show message: {e}")


def main():
    """Main application entry point."""
    logger.info("Starting ApiPostgresConnector...")

    if not acquire_single_instance():
        logger.warning("Another instance is already running, exiting")
        _show_already_running_message()
        return

    # Гарантируем наличие API-ключа у каждого подключения
    # (до создания GUI — чтобы ключ был виден во вкладке «Подключения»)
    for connection in list(config.connections):
        name = connection.get("name")
        if not name:
            continue
        try:
            config.ensure_api_key(name)
        except Exception as e:
            logger.warning(f"Failed to ensure API key for '{name}': {e}")

    # Create GUI first (we need it for activity callback)
    gui = MainWindow(api_server=None)
    
    # Create API server with GUI reference for activity callbacks
    api_server = APIServer(gui_reference=gui)
    
    # Connect GUI to API server
    gui.api_server = api_server
    
    # Connect GUI to API routes for activity callbacks
    import src.api.routes as routes_module
    routes_module._gui_reference = gui
    
    # Auto-start API if configured
    if config.app.get("auto_start_api", True):
        started = api_server.start()
        logger.info("API server auto-started" if started else "API server failed to start")
    
    gui.run()

    # Cleanup
    api_server.stop()
    logger.info("ApiPostgresConnector closed")


if __name__ == "__main__":
    main()
