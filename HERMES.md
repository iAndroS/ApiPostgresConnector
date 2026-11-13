# ApiPostgresConnector

**ApiPostgresConnector** — десктопное приложение с графическим интерфейсом (CustomTkinter) и встроенным REST API (Flask) для работы с PostgreSQL. Приложение собирается в исполняемый EXE-файл через PyInstaller.

## Технологический стек

| Компонент       | Технологии                                      |
|-----------------|------------------------------------------------|
| GUI             | CustomTkinter 5.2.2                            |
| REST API        | Flask 3.1.1, flask-cors                        |
| База данных     | psycopg2-binary 2.9.10, PostgreSQL             |
| Безопасность    | cryptography (Fernet), API Key auth            |
| Системный трей  | pystray, Pillow                                |
| Сборка          | PyInstaller 6.14.1                             |

## Основные возможности

- Подключение к PostgreSQL через DSN-строку формата `postgres://user:pass@host:port/db`
- REST API с аутентификацией по заголовку `X-API-Key` (защищены все эндпоинты, кроме `/health` и `/info`)
- Шифрование паролей через Fernet для безопасного хранения в `config/settings.json`
- Выполнение SQL-запросов (только SELECT) через эндпоинт `/api/v1/query`
- Массовая вставка записей через `/api/v1/tables/<table>/batch-insert` (до 1000 записей)
- Системный трей с отображением статуса API и времени последней активности
- Автоматическое переподключение к базе данных при разрыве соединения
- Поддержка вставки из буфера обмена (Ctrl+V)