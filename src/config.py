"""Configuration module for ApiPostgresConnector."""
import base64
import hashlib
import json
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import cryptography, but make it optional
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    Fernet = None


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
    """Application configuration manager."""

    def __init__(self):
        self._config = {}
        
        # Determine base path depending on whether running from pyinstaller
        if getattr(sys, 'frozen', False):
            # Running from pyinstaller - config is in the app directory
            self._base_path = Path(sys._MEIPASS)
        else:
            # Running from source
            self._base_path = Path(__file__).parent.parent
            
        self._config_path = self._base_path / "config" / "settings.json"
        self.load()

    def load(self):
        """Load configuration from JSON file."""
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            self._config = self._get_default_config()
        
        # Decrypt password if present
        if self._config.get("database", {}).get("password"):
            self._config["database"]["password"] = decrypt_password(
                self._config["database"]["password"]
            )

    def save(self):
        """Save configuration to JSON file."""
        # Encrypt password before saving
        config_to_save = self._config.copy()
        if config_to_save.get("database", {}).get("password"):
            config_to_save["database"]["password"] = encrypt_password(
                config_to_save["database"]["password"]
            )
        
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(config_to_save, f, indent=2, ensure_ascii=False)

    def _get_default_config(self):
        """Get default configuration."""
        return {
            "database": {
                "host": "localhost",
                "port": 5432,
                "database": "postgres",
                "user": "postgres",
                "password": ""
            },
            "api": {
                "host": "127.0.0.1",
                "port": 5000,
                "debug": False,
                "api_keys": []
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

    @property
    def database(self) -> dict:
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

    def update_database(self, **kwargs):
        """Update database configuration."""
        self._config.setdefault("database", {}).update(kwargs)

    def update_api(self, **kwargs):
        """Update API configuration."""
        self._config.setdefault("api", {}).update(kwargs)

    def update_gui(self, **kwargs):
        """Update GUI configuration."""
        self._config.setdefault("gui", {}).update(kwargs)


# Global config instance
config = Config()
