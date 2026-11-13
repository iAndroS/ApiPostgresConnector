# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Проект

ApiPostgresConnector — десктопное приложение (CustomTkinter GUI + Flask API в одном процессе) для работы с PostgreSQL через REST API. Собирается в EXE через PyInstaller.

Поддерживает **несколько именованных подключений**: у каждого свои параметры БД и свои API-ключи. Клиент выбирает подключение именем в URL: `/api/v1/c/<имя>/...`.

## Возможности

- **DSN подключение** — поддержка строки подключения в формате `postgres://user:pass@host:port/db`
- **Системный трей** — меню с быстрыми действиями и отображением статуса API
- **API Key аутентификация** — защита эндпоинтов через заголовок `X-API-Key` (ключ привязан к подключению)
- **Шифрование паролей** — безопасное хранение паролей через Fernet (cryptography)
- **Вставка из буфера обмена** — поддержка Ctrl+V для вставки данных
- **Диагностика ошибок БД** — причина ошибки в логе, в GUI и в ответах API

## Команды

- Запуск: `python src/app.py`
- Сборка EXE: `pyinstaller pyinstaller.spec` (результат в `dist/ApiPostgresConnector_v2/`)
- Установка зависимостей: `pip install -r requirements.txt` (инструменты — `requirements-dev.txt`)
- Запуск тестов: `pytest tests/ -v`

## Архитектура

```
GUI (MainWindow) → APIServer (werkzeug make_server в потоке) → Flask (Blueprint)
    → ConnectionRegistry (реестр подключений) → Database (psycopg2)
```

- `src/config.py` — конфиг (список подключений + глобальные настройки сервера), шифрование паролей
- `src/api/connections.py` — `ConnectionRegistry` и `ConnectionProfile` (БД + ключи подключения)
- `src/api/database.py` — работа с PostgreSQL, классификация ошибок (`describe_db_error`), `last_error`
- `src/api/routes.py` — эндпоинты; активное подключение запроса лежит в `flask.g`
- `src/gui/main_window.py` — вкладки «Подключения», «API», «Документация API»

## Критические особенности

- **Сервер** — `werkzeug.serving.make_server` (не `app.run`): `stop()` реально освобождает порт,
  `start()` возвращает `False`, если порт занят. Перед привязкой проверяется занятость порта,
  потому что на Windows `SO_REUSEADDR` позволяет второму экземпляру «успешно» занять порт.
- **Подключения** — выбор БД по имени в URL (`/api/v1/c/<имя>/...`); без имени — `default_connection`.
  Ключ проверяется **в рамках подключения**, глобального `API_KEYS` больше нет.
- **Hot-reload** — `MainWindow._save_settings()` → `config.save()` → `registry.reload(config)`:
  ключи и параметры БД применяются к работающему серверу без перезапуска.
- **`/api/v1/query` принимает только SELECT** — другие SQL-команды блокируются на уровне роутов.
- **API требует X-API-Key header** — все эндпоинты защищены, кроме `/health` и `/info` (и только для
  подключения по умолчанию: именованные `/c/<имя>/...` всегда требуют ключ).
- **Причина ошибки БД** — брать из `Database.last_error` (dict: kind/message/detail/hint/sqlstate/user_hint),
  а не из строковых сравнений и не из обобщённых сообщений.
- **Шифрование паролей через Fernet** — пароли в config/settings.json хранятся в зашифрованном виде;
  ключ по умолчанию выводится из `platform.node()`, для переноса задавай `ENCRYPTION_KEY`.
- **Путь конфига** — `get_base_dir()`: frozen → папка рядом с EXE, dev → корень проекта;
  при отсутствии прав на запись — fallback в `%APPDATA%\ApiPostgresConnector\config\settings.json`.
- **`config/settings.json` не коммитится** (в репозитории только `config/settings.default.json`).
- **Валидация идентификаторов** — все ID проходят проверку на корректность перед использованием в запросах.
- **Batch-insert** — массовая вставка через `/api/v1/tables/<table>/batch-insert` (макс. 1000 записей);
  набор колонок у всех объектов должен совпадать, иначе 400.
- **PyInstaller-совместимость** — в `datas` только `config/settings.default.json`; исходники в PYZ.
- **GUI обновляет статус API каждые 2 секунды** через `after()` — учитывай при отладке утечек.
- **Тесты** — в `tests/` только юнит-тесты (без окон и без реальной БД); отладочные GUI-скрипты
  лежат в `tests/manual/` и pytest их не собирает.
