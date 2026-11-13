"""Единый источник версии приложения.

Используется в GUI, ответах API, встроенной HTML-документации и в
`pyinstaller.spec` (ресурс версии EXE — свойства файла в Windows).
"""

APP_NAME = "ApiPostgresConnector"
APP_VERSION = "2.1.0"

# Версия в формате Windows (major.minor.micro.build)
APP_VERSION_TUPLE = (2, 1, 0, 0)

VERSION_STRING = f"{APP_NAME} v{APP_VERSION}"
