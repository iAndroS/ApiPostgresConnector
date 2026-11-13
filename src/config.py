"""Configuration module for ApiPostgresConnector."""
import base64
import copy
import hashlib
import json
import logging
import os
import platform
import secrets
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Имя каталога приложения в %APPDATA% (используется как fallback для конфига)
APP_DIR_NAME = "ApiPostgresConnector"

# Имя подключения, создаваемого при миграции со старой (одно-подключение) схемы
DEFAULT_CONNECTION_NAME = "По умолчанию"

# Try to import cryptography, but make it optional
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    Fernet = None


def get_base_dir() -> Path:
    """Каталог, рядом с которым хранится пользовательский конфиг.

    В собранном (frozen) приложении — папка рядом с EXE,
    в режиме разработки — корень проекта.

    Returns:
        Path: каталог с пользовательским конфигом
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_appdata_dir() -> Path:
    """Каталог приложения в %APPDATA% (fallback, если рядом с EXE нет прав на запись).

    Returns:
        Path: каталог %APPDATA%\\ApiPostgresConnector
    """
    base = os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_DIR_NAME


def get_bundled_config_path() -> Optional[Path]:
    """Путь к конфигу-шаблону внутри собранного приложения.

    Returns:
        Optional[Path]: путь к settings.default.json в _MEIPASS или None
    """
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys._MEIPASS) / "config" / "settings.default.json"


def get_legacy_bundled_config_path() -> Optional[Path]:
    """Путь к старому пользовательскому конфигу внутри _MEIPASS (миграция сборок).

    Returns:
        Optional[Path]: путь к settings.json в _MEIPASS или None
    """
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys._MEIPASS) / "config" / "settings.json"


def get_fernet() -> Optional[Fernet]:
    """Создаёт Fernet из machine_id или переменной окружения.
    
    Returns:
        Fernet instance или None если cryptography недоступна
    """
    if not CRYPTO_AVAILABLE:
        return None
    
    # Получаем ключ из переменной окружения или генерируем из machine_id
    key = os.environ.get('ENCRYPTION_KEY')
    if key:
        # Используем ключ из env (должен быть в base64)
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            logger.warning(f"Failed to create Fernet from ENCRYPTION_KEY: {e}")
    
    # Генерируем ключ из machine_id
    machine_id = platform.node().encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(machine_id).digest())
    return Fernet(key)


def encrypt_password(password: str) -> str:
    """Шифрует пароль.

    Args:
        password: Пароль для шифрования
        
    Returns:
        Зашифрованный пароль в base64 или исходный если ошибка
    """
    if not password:
        return password
    
    if not CRYPTO_AVAILABLE:
        return password
    
    try:
        fernet = get_fernet()
        if fernet:
            encrypted = fernet.encrypt(password.encode())
            return base64.b64encode(encrypted).decode()
    except Exception:
        pass
    
    return password


def decrypt_password(encrypted_password: str) -> str:
    """Расшифровывает пароль.

    Args:
        encrypted_password: Зашифрованный пароль
        
    Returns:
        Расшифрованный пароль или исходный если ошибка
    """
    if not encrypted_password:
        return encrypted_password
    
    if not CRYPTO_AVAILABLE:
        return encrypted_password
    
    try:
        fernet = get_fernet()
        if fernet:
            # Пробуем декодировать из base64
            try:
                decoded = base64.b64decode(encrypted_password.encode())
                decrypted = fernet.decrypt(decoded)
                return decrypted.decode('utf-8')
            except UnicodeDecodeError as e:
                logger.warning(f"UnicodeDecodeError during password decryption: {e}")
                return encrypted_password
            except Exception:
                # Если не в base64, возможно пароль не был зашифрован
                return encrypted_password
    except Exception as e:
        logger.error(f"Unexpected error in decrypt_password: {type(e).__name__}: {e}")
    
    return encrypted_password


class Config:
    """Application configuration manager.

    Схема конфига (актуальная):

    {
        "connections": [
            {
                "name": "По умолчанию",
                "database": {"host": ..., "port": ..., "database": ..., "user": ..., "password": ...},
                "api_keys": ["..."],
                "enabled": true
            }
        ],
        "default_connection": "По умолчанию",
        "api": {"host": "127.0.0.1", "port": 5000, "debug": false},
        "gui": {...},
        "app": {...}
    }
    """

    def __init__(self):
        self._base_path = get_base_dir()
        self._config_path = self._base_path / "config" / "settings.json"
        self._fallback_path = get_appdata_dir() / "config" / "settings.json"
        self._config: Dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------
    # Загрузка / сохранение
    # ------------------------------------------------------------------

    def load(self):
        """Load configuration from JSON file."""
        existing = self._find_existing_config()
        
        if existing:
            try:
                with open(existing, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                logger.info(f"Configuration loaded from {existing}")
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Failed to read configuration from {existing}: {e}")
                self._config = self._get_default_config()
        else:
            self._config = self._get_default_config()
            self._seed_config_file()
        
        self._migrate_legacy_schema()
        self._normalize_connections()
        self._decrypt_passwords()
    
    def save(self):
        """Save configuration to JSON file."""
        # Глубокая копия: иначе шифрование пароля вложенных подключений
        # изменит и в памяти (повторное сохранение зашифрует шифротекст)
        config_to_save = copy.deepcopy(self._config)
        
        for connection in config_to_save.get("connections", []):
            password = connection.get("database", {}).get("password")
            if password:
                connection["database"]["password"] = encrypt_password(password)
        
        self._write_json(config_to_save)
    
    def _find_existing_config(self) -> Optional[Path]:
        """Ищет существующий файл конфига (рядом с EXE, затем в %APPDATA%)."""
        for candidate in (self._config_path, self._fallback_path):
            if candidate.exists():
                return candidate
        return None
    
    def _seed_config_file(self):
        """Создаёт файл конфига при первом запуске (копия шаблона из сборки)."""
        source = get_legacy_bundled_config_path() or get_bundled_config_path()
        
        if source and source.exists():
            try:
                self._config_path.parent.mkdir(parents=True, exist_ok=True)
                content = source.read_text(encoding="utf-8")
                self._write_text(content)
                logger.info(f"Configuration seeded from {source}")
                return
            except OSError as e:
                logger.warning(f"Failed to seed configuration from {source}: {e}")
        
        try:
            self._write_json(self._config)
            logger.info(f"Default configuration created at {self._config_path}")
        except OSError as e:
            logger.warning(f"Failed to create default configuration: {e}")
    
    def _write_text(self, content: str):
        """Записывает текст в файл конфига (атомарно, с fallback в %APPDATA%)."""
        self._write_to_path(self._config_path, content)
    
    def _write_json(self, data: Dict[str, Any]):
        """Сериализует и записывает конфиг (атомарно, с fallback в %APPDATA%)."""
        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._write_to_path(self._config_path, content)
    
    def _write_to_path(self, path: Path, content: str):
        """Атомарная запись файла с fallback в %APPDATA% при отказе в правах."""
        try:
            self._atomic_write(path, content)
            return
        except PermissionError:
            logger.warning(f"No write permission for {path}, falling back to {self._fallback_path}")
            self._config_path = self._fallback_path
            self._atomic_write(self._fallback_path, content)
            return
        except OSError as e:
            logger.warning(f"Failed to write {path}: {e}, falling back to {self._fallback_path}")
            self._config_path = self._fallback_path
            self._atomic_write(self._fallback_path, content)
            return
    
    @staticmethod
    def _atomic_write(path: Path, content: str):
        """Пишет содержимое во временный файл рядом и заменяет целевой (atomic replace)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(path.name + ".tmp")
        try:
            tmp_path.write_text(content, encoding="utf-8")
            os.replace(tmp_path, path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
    
    def _migrate_legacy_schema(self):
        """Переводит старую схему (database + api.api_keys) в список подключений."""
        if self._config.get("connections"):
            # Схема уже новая — проверяем корректность имени по умолчанию
            names = [c.get("name") for c in self._config["connections"]]
            default = self._config.get("default_connection")
            if default not in names:
                self._config["default_connection"] = names[0] if names else DEFAULT_CONNECTION_NAME
            return
        
        legacy_database = self._config.get("database")
        
        if legacy_database:
            legacy_keys = self._config.get("api", {}).get("api_keys", []) or []
            self._config["connections"] = [{
                "name": DEFAULT_CONNECTION_NAME,
                "database": dict(legacy_database),
                "api_keys": list(legacy_keys)
            }]
            self._config["default_connection"] = DEFAULT_CONNECTION_NAME
            logger.info(f"Configuration migrated to multi-connection schema "
                        f"(connection '{DEFAULT_CONNECTION_NAME}')")
        
        # Убираем legacy-поля, чтобы они не дублировались при сохранении
        self._config.pop("database", None)
        self._config.get("api", {}).pop("api_keys", None)
    
    def _normalize_connections(self):
        """Дополняет подключения недостающими полями (enabled, api_keys)."""
        for connection in self._config.get("connections", []):
            if "enabled" not in connection:
                connection["enabled"] = True
            connection.setdefault("api_keys", [])

    def _decrypt_passwords(self):
        """Расшифровывает пароли всех подключений."""
        for connection in self._config.get("connections", []):
            password = connection.get("database", {}).get("password")
            if password:
                connection["database"]["password"] = decrypt_password(password)
    
    def _get_default_config(self):
        """Get default configuration."""
        return {
            "connections": [
                {
                    "name": DEFAULT_CONNECTION_NAME,
                    "database": {
                        "host": "localhost",
                        "port": 5432,
                        "database": "postgres",
                        "user": "postgres",
                        "password": ""
                    },
                    "api_keys": [],
                    "enabled": True
                }
            ],
            "default_connection": DEFAULT_CONNECTION_NAME,
            "api": {
                "host": "127.0.0.1",
                "port": 5000,
                "debug": False,
                "require_auth": True
            },
            "gui": {
                "theme": "dark-blue",
                "width": 600,
                "height": 500
            },
            "app": {
                "auto_start_api": True,
                "minimize_to_tray": True,
                "enable_logging": True
            }
        }
    
    # ------------------------------------------------------------------
    # Доступ к разделам конфига
    # ------------------------------------------------------------------
    
    @property
    def database(self) -> dict:
        """Параметры БД подключения по умолчанию (совместимость со старым кодом)."""
        connection = self.get_connection(self.default_connection)
        if connection:
            return connection.get("database", {})
        return self._config.get("database", {})
    
    @property
    def api(self) -> dict:
        return self._config.get("api", {})
    
    @property
    def gui(self) -> dict:
        return self._config.get("gui", {})
    
    @property
    def app(self) -> dict:
        return self._config.get("app", {})
    
    @property
    def connections(self) -> List[Dict[str, Any]]:
        """Список подключений (БД + свои API-ключи)."""
        connections = self._config.setdefault("connections", [])
        if not connections:
            connections.append(self._get_default_config()["connections"][0])
        return connections
    
    @property
    def default_connection(self) -> str:
        """Имя подключения по умолчанию."""
        names = [c.get("name") for c in self._config.get("connections", [])]
        default = self._config.get("default_connection")
        if default and default in names:
            return default
        return names[0] if names else DEFAULT_CONNECTION_NAME
    
    @default_connection.setter
    def default_connection(self, name: str):
        self.set_default_connection(name)
    
    # ------------------------------------------------------------------
    # Управление подключениями
    # ------------------------------------------------------------------
    
    def get_connection(self, name: str) -> Optional[Dict[str, Any]]:
        """Возвращает подключение по имени или None."""
        for connection in self._config.get("connections", []):
            if connection.get("name") == name:
                return connection
        return None
    
    def get_connection_names(self) -> List[str]:
        """Список имён подключений."""
        return [c.get("name") for c in self._config.get("connections", [])]
    
    def add_connection(self, name: str, database: Optional[dict] = None, 
                       api_keys: Optional[List[str]] = None,
                       enabled: bool = True) -> Dict[str, Any]:
        """Добавляет новое подключение.

        Args:
            name: Имя подключения (должно быть уникальным)
            database: Параметры БД
            api_keys: Список API-ключей
            enabled: Включено ли подключение (True) или отключено (False)
            
        Returns:
            Созданное подключение
            
        Raises:
            ValueError: если имя уже занято
        """
        name = (name or "").strip()
        if not name:
            raise ValueError("Connection name cannot be empty")
        if self.get_connection(name):
            raise ValueError(f"Connection '{name}' already exists")
        
        connection = {
            "name": name,
            "database": dict(database) if database else {
                "host": "localhost",
                "port": 5432,
                "database": "postgres",
                "user": "postgres",
                "password": ""
            },
            "api_keys": list(api_keys) if api_keys else [],
            "enabled": bool(enabled)
        }
        self._config.setdefault("connections", []).append(connection)
        
        if not self._config.get("default_connection"):
            self._config["default_connection"] = name
        
        return connection
    
    def update_connection(self, name: str, database: Optional[dict] = None,
                          api_keys: Optional[List[str]] = None,
                          enabled: Optional[bool] = None):
        """Обновляет параметры подключения."""
        connection = self.get_connection(name)
        if not connection:
            raise ValueError(f"Unknown connection '{name}'")
        
        if database is not None:
            connection.setdefault("database", {}).update(database)
        if api_keys is not None:
            connection["api_keys"] = list(api_keys)
        if enabled is not None:
            connection["enabled"] = bool(enabled)
    
    def set_connection_enabled(self, name: str, enabled: bool) -> bool:
        """Включает или отключает подключение.

        Args:
            name: Имя подключения
            enabled: True — включить, False — отключить

        Returns:
            bool: Итоговое состояние подключения

        Raises:
            ValueError: если подключение не найдено
        """
        connection = self.get_connection(name)
        if not connection:
            raise ValueError(f"Unknown connection '{name}'")
        
        connection["enabled"] = bool(enabled)
        
        return bool(enabled)
    
    def is_connection_enabled(self, name: str) -> bool:
        """Проверяет, включено ли подключение (по умолчанию — включено)."""
        connection = self.get_connection(name)
        if not connection:
            return False
        
        return bool(connection.get("enabled", True))
    
    def rename_connection(self, name: str, new_name: str):
        """Переименовывает подключение."""
        connection = self.get_connection(name)
        new_name = (new_name or "").strip()
        
        if not connection:
            raise ValueError(f"Unknown connection '{name}'")
        if not new_name:
            raise ValueError("Connection name cannot be empty")
        if new_name != name and self.get_connection(new_name):
            raise ValueError(f"Connection '{new_name}' already exists")
        
        connection["name"] = new_name
        
        if self._config.get("default_connection") == name:
            self._config["default_connection"] = new_name
    
    def remove_connection(self, name: str) -> bool:
        """Удаляет подключение. Последнее удалять нельзя."""
        connections = self._config.get("connections", [])
        
        if len(connections) <= 1:
            logger.warning("Cannot remove the last connection")
            return False
        
        connection = self.get_connection(name)
        if not connection:
            return False
        
        self._config["connections"] = [c for c in connections if c.get("name") != name]
        
        if self._config.get("default_connection") == name:
            self._config["default_connection"] = self._config["connections"][0].get("name")
        
        return True
    
    def set_default_connection(self, name: str):
        """Назначает подключение по умолчанию."""
        if not self.get_connection(name):
            raise ValueError(f"Unknown connection '{name}'")
        self._config["default_connection"] = name
    
    def ensure_api_key(self, name: str) -> str:
        """Гарантирует наличие API-ключа у подключения (генерирует при необходимости).

        Args:
            name: Имя подключения
            
        Returns:
            API-ключ подключения
        """
        connection = self.get_connection(name)
        if not connection:
            raise ValueError(f"Unknown connection '{name}'")
        
        api_keys = connection.setdefault("api_keys", [])
        
        if not api_keys:
            new_key = secrets.token_urlsafe(32)
            api_keys.append(new_key)
            logger.info(f"Generated new API key for connection '{name}': {new_key[:8]}...")
            try:
                self.save()
            except OSError as e:
                logger.warning(f"Failed to save generated API key: {e}")
            return new_key
        
        return api_keys[0]
    
    def set_api_key(self, name: str, key: str) -> str:
        """Задаёт единственный API-ключ подключения (старые ключи отбрасываются).

        Args:
            name: Имя подключения
            key: Новый ключ

        Returns:
            Установленный ключ

        Raises:
            ValueError: если подключение не найдено
        """
        connection = self.get_connection(name)
        if not connection:
            raise ValueError(f"Unknown connection '{name}'")
        
        connection["api_keys"] = [key] if key else []
        
        return key
    
    def update_database(self, **kwargs):
        """Update database configuration of the default connection."""
        connection = self.get_connection(self.default_connection)
        if connection:
            connection.setdefault("database", {}).update(kwargs)
        else:
            self._config.setdefault("database", {}).update(kwargs)
    
    def update_api(self, **kwargs):
        """Update API configuration."""
        self._config.setdefault("api", {}).update(kwargs)
    
    def update_gui(self, **kwargs):
        """Update GUI configuration."""
        self._config.setdefault("gui", {}).update(kwargs)
    
    def update_app(self, **kwargs):
        """Update application configuration."""
        self._config.setdefault("app", {}).update(kwargs)


# Global config instance
config = Config()
