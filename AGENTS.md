# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Проект

ApiPostgresConnector — десктопное приложение (CustomTkinter GUI + Flask API в одном процессе) для работы с PostgreSQL через REST API. Собирается в EXE через PyInstaller.

## Возможности

- **DSN подключение** — поддержка строки подключения в формате `postgres://user:pass@host:port/db`
- **Системный трей** — меню с быстрыми действиями и отображением статуса API
- **API Key аутентификация** — защита эндпоинтов через заголовок `X-API-Key`
- **Шифрование паролей** — безопасное хранение паролей через Fernet (cryptography)
- **Вставка из буфера обмена** — поддержка Ctrl+V для вставки данных

## Команды

- Запуск: `python src/app.py`
- Сборка EXE: `pyinstaller pyinstaller.spec` (результат в `build/pyinstaller/`)
- Установка зависимостей: `pip install -r requirements.txt`
- Запуск тестов: `pytest tests/`

## Критические особенности

- **Flask запускается в daemon-потоке** внутри GUI-приложения — нет graceful shutdown
- **Глобальная переменная `db_instance`** в `src/api/routes.py` — инициализируется через `init_routes(database)`
- **PyInstaller-совместимость**: все модули используют `sys._MEIPASS` для определения путей при frozen-режиме
- **`/api/v1/query` принимает только SELECT** — другие SQL-команды блокируются на уровне роутов
- **config/settings.json** включается в PyInstaller-сборку как data-файл, путь определяется динамически
- **GUI обновляет статус API каждые 2 секунды** через `after()` — учитывай при отладке утечек
- **API требует X-API-Key header** — все эндпоинты защищены, кроме `/health` и `/info`
- **Шифрование паролей через Fernet** — пароли в config/settings.json хранятся в зашифрованном виде
- **Валидация идентификаторов** — все ID проходят проверку на корректность перед использованием в запросах
