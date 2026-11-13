"""Общие фикстуры для тестов.

GUI-тесты работают с конфигом приложения, поэтому он изолируется от рабочего
файла config/settings.json: изменения остаются только в памяти и во временном
файле, реальные настройки пользователя не затрагиваются.
"""
import copy
import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def isolated_config():
    """Изолирует конфиг приложения от рабочего файла.

    Returns:
        Экземпляр Config приложения
    """
    from src.config import config

    original_config = copy.deepcopy(config._config)
    original_path = config._config_path
    original_fallback = config._fallback_path

    temp_path = Path(tempfile.gettempdir()) / "api_postgres_connector_gui_test.json"

    config._config_path = temp_path
    config._fallback_path = temp_path

    yield config

    config._config = original_config
    config._config_path = original_path
    config._fallback_path = original_fallback

    if temp_path.exists():
        try:
            temp_path.unlink()
        except OSError:
            pass
