"""Registry of named database connections.

Каждое подключение — имя + свои параметры БД + свой набор API-ключей.
Клиент выбирает подключение именем в URL: /api/v1/c/<имя>/tables
"""
import logging
import threading
from typing import Any, Dict, List, Optional

from .database import Database

logger = logging.getLogger(__name__)


def db_signature(db_config: Optional[Dict[str, Any]]) -> tuple:
    """Сигнатура параметров подключения (для определения, нужно ли пересоздавать Database).

    Args:
        db_config: Параметры БД

    Returns:
        tuple, по которому можно сравнивать два набора параметров
    """
    db_config = db_config or {}
    return (
        db_config.get("host"),
        db_config.get("port"),
        db_config.get("database"),
        db_config.get("user"),
        db_config.get("password"),
    )


class ConnectionProfile:
    """Именованное подключение: свои параметры БД и свои API-ключи."""

    def __init__(self, name: str, database_config: Optional[Dict[str, Any]] = None,
                 api_keys: Optional[List[str]] = None, enabled: bool = True):
        self.name = name
        self.database_config = dict(database_config or {})
        self.api_keys = list(api_keys or [])
        self.enabled = bool(enabled)
        self._db: Optional[Database] = None
        self._lock = threading.Lock()

    @property
    def db(self) -> Database:
        """Подключение к БД (создаётся лениво при первом обращении)."""
        with self._lock:
            if self._db is None:
                self._db = Database(self.database_config)
            return self._db

    @property
    def is_db_created(self) -> bool:
        """True если подключение к БД уже создано (без попытки создать его)."""
        return self._db is not None

    @property
    def last_error(self) -> Optional[Dict[str, Any]]:
        """Последняя ошибка подключения к БД (если подключение создавалось)."""
        return self._db.get_last_error() if self._db else None

    @property
    def last_error_message(self) -> Optional[str]:
        """Краткое описание последней ошибки подключения."""
        return self._db.last_error_message if self._db else None

    def has_key(self, key: str) -> bool:
        """Проверяет, что ключ принадлежит этому подключению."""
        return bool(key) and key in self.api_keys

    def signature(self) -> tuple:
        """Сигнатура параметров БД (для сравнения при перезагрузке реестра)."""
        return db_signature(self.database_config)

    def close_db(self, reason: str = ""):
        """Закрывает подключение к БД.

        Args:
            reason: Причина закрытия (для лога)
        """
        with self._lock:
            if self._db is not None:
                self._db.close(reason=reason)
                self._db = None

    def set_db(self, db: Database):
        """Подменяет объект подключения к БД (используется в тестах)."""
        with self._lock:
            self._db = db

    def __repr__(self) -> str:
        return f"<ConnectionProfile {self.name}>"


class ConnectionRegistry:
    """Реестр подключений приложения."""

    def __init__(self, config: Any = None):
        self._lock = threading.RLock()
        self._profiles: Dict[str, ConnectionProfile] = {}
        self._default_name = ""
        
        # Требуется ли API-ключ для запросов (общий переключатель приложения)
        self.require_auth = True
        
        if config is not None:
            self.reload(config)

    def reload(self, config: Any):
        """Перестраивает реестр из конфига.

        Пересоздаёт Database только для подключений, у которых изменились параметры БД;
        ключи обновляются всегда. Подключения, удалённые из конфига, закрываются.

        Args:
            config: Экземпляр src.config.Config
        """
        connections = list(getattr(config, "connections", []) or [])
        default_name = getattr(config, "default_connection", "") or ""
        
        api_config = getattr(config, "api", {}) or {}
        self.require_auth = bool(api_config.get("require_auth", True))
        
        new_profiles: Dict[str, ConnectionProfile] = {}
        
        for connection in connections:
            name = (connection.get("name") or "").strip()
            if not name:
                continue
            
            db_config = connection.get("database", {}) or {}
            api_keys = list(connection.get("api_keys", []) or [])
            enabled = bool(connection.get("enabled", True))
            
            old_profile = self._profiles.get(name)
            
            if old_profile and old_profile.signature() == db_signature(db_config):
                old_profile.api_keys = api_keys
                old_profile.enabled = enabled
                new_profiles[name] = old_profile
            else:
                if old_profile:
                    logger.info(f"Database parameters changed for connection '{name}', reconnecting")
                    old_profile.close_db(reason="settings changed")
                new_profiles[name] = ConnectionProfile(name, db_config, api_keys, enabled)
        
        for name, profile in self._profiles.items():
            if name not in new_profiles:
                logger.info(f"Connection '{name}' removed, closing database connection")
                profile.close_db(reason="connection removed")
        
        with self._lock:
            self._profiles = new_profiles
            self._default_name = default_name if default_name in new_profiles else ""
            
            if not self._default_name and new_profiles:
                self._default_name = next(iter(new_profiles))
        
        logger.info(f"Connection registry reloaded: {', '.join(self.names()) or 'empty'}")

    def get(self, name: str) -> Optional[ConnectionProfile]:
        """Возвращает подключение по имени или None."""
        with self._lock:
            return self._profiles.get(name)

    def get_default(self) -> Optional[ConnectionProfile]:
        """Возвращает подключение по умолчанию."""
        with self._lock:
            if not self._default_name:
                return None
            return self._profiles.get(self._default_name)

    @property
    def default_name(self) -> str:
        """Имя подключения по умолчанию."""
        with self._lock:
            return self._default_name

    def names(self) -> List[str]:
        """Список имён подключений."""
        with self._lock:
            return list(self._profiles.keys())

    def total_key_count(self) -> int:
        """Общее количество API-ключей во всех подключениях."""
        with self._lock:
            return sum(len(profile.api_keys) for profile in self._profiles.values())

    def close_all(self):
        """Закрывает все подключения к БД (при выходе из приложения)."""
        with self._lock:
            for profile in self._profiles.values():
                profile.close_db(reason="application exit")
    
    def start_background_connect(self):
        """Подключается ко всем подключениям в фоновом потоке.

        Нужен, чтобы состояние соединения было известно (например, для /health),
        не блокируя запуск приложения и HTTP-запросы.

        Returns:
            threading.Thread: запущенный поток (daemon)
        """
        def worker():
            with self._lock:
                profiles = list(self._profiles.values())
            
            for profile in profiles:
                if not profile.enabled:
                    logger.info(f"Skipping background connect for disabled connection '{profile.name}'")
                    continue
                
                try:
                    profile.db
                except Exception as e:
                    logger.warning(f"Background connect failed for '{profile.name}': {e}")
        
        thread = threading.Thread(target=worker, daemon=True, name="db-background-connect")
        thread.start()
        
        return thread
