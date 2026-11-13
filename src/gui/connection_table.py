"""Таблица подключений для вкладки «Подключения».

Таблица нарисована на Canvas: так статус подключения показывается цветной точкой
в отдельной ячейке, а в строке стоят иконки действий — копирование ключа,
выпуск нового ключа и включение/отключение подключения.
В ttk.Treeview цвет задаётся для всей строки, отдельную ячейку покрасить нельзя.
"""
import logging
import math
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

logger = logging.getLogger(__name__)

# Цвета элементов таблицы
BG_HEADER = "#3a3a3a"
BG_ROW = "#2b2b2b"
BG_ROW_SELECTED = "#3d5a80"
FG_TEXT = "#ffffff"
FG_MUTED = "#b0b0b0"
FG_ACCENT = "#4a9eff"
FG_OK = "#3fae4f"
FG_OFF = "#5a5a5a"


class ConnectionTable(ctk.CTkFrame):
    """Список подключений: имя, хост, порт, база, пользователь, статус, ключ, вкл/выкл."""

    # (ключ, заголовок, ширина, выравнивание)
    COLUMNS = (
        ("name", "Имя", 115, "w"),
        ("host", "Хост", 100, "w"),
        ("port", "Порт", 45, "w"),
        ("db", "База", 65, "w"),
        ("user", "Пользователь", 110, "w"),
        ("status", "Статус", 100, "w"),
        ("key", "Ключ", 70, "center"),
        ("enabled", "Вкл", 50, "center"),
    )

    ROW_HEIGHT = 28
    HEADER_HEIGHT = 26
    FONT_SIZE = 11

    def __init__(self, master, visible_rows: int = 4,
                 on_select: Optional[Callable[[str], None]] = None,
                 on_copy_key: Optional[Callable[[str], None]] = None,
                 on_regenerate_key: Optional[Callable[[str], None]] = None,
                 on_toggle: Optional[Callable[[str], None]] = None):
        """Создаёт таблицу подключений.

        Args:
            master: Родительский виджет
            visible_rows: Сколько строк видно без прокрутки
            on_select: Обработчик выбора строки (имя подключения)
            on_copy_key: Обработчик клика по иконке копирования ключа
            on_regenerate_key: Обработчик клика по иконке выпуска нового ключа
            on_toggle: Обработчик клика по переключателю вкл/выкл
        """
        super().__init__(master, fg_color="transparent")

        self._rows: List[Dict] = []
        self._selected: Optional[str] = None
        self._scroll_row = 0
        self._on_select = on_select
        self._on_copy_key = on_copy_key
        self._on_regenerate_key = on_regenerate_key
        self._on_toggle = on_toggle

        self._font = tkfont.Font(family="Segoe UI", size=self.FONT_SIZE)
        self._bold_font = tkfont.Font(family="Segoe UI", size=self.FONT_SIZE, weight="bold")

        self._offsets: Dict[str, int] = {}
        self._widths: Dict[str, int] = {}
        offset = 0
        for key, _title, width, _anchor in self.COLUMNS:
            self._offsets[key] = offset
            self._widths[key] = width
            offset += width
        self._total_width = offset

        self._canvas = tk.Canvas(
            self,
            width=self._total_width,
            height=self.HEADER_HEIGHT + visible_rows * self.ROW_HEIGHT,
            bg=BG_ROW,
            highlightthickness=0,
            bd=0,
        )
        self._canvas.pack(side="left", fill="both", expand=True)

        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Configure>", lambda e: self._redraw())

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------

    def set_rows(self, rows: List[Dict]):
        """Обновляет содержимое таблицы.

        Args:
            rows: Список словарей с полями name, host, port, db, user,
                status_color, status_text, has_key, enabled
        """
        self._rows = list(rows or [])
        self._clamp_scroll()
        self._redraw()

    def get_rows(self) -> List[Dict]:
        """Текущие строки таблицы."""
        return list(self._rows)

    def select(self, name: Optional[str]):
        """Выделяет строку подключения (без вызова обработчика выбора)."""
        self._selected = name
        self._redraw()

    def get_selected(self) -> Optional[str]:
        """Имя выделенного подключения."""
        return self._selected

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------

    def _clamp_scroll(self):
        """Ограничивает прокрутку доступными строками."""
        max_row = max(0, len(self._rows) - 1)
        self._scroll_row = max(0, min(self._scroll_row, max_row))

    def _redraw(self):
        """Перерисовывает таблицу."""
        canvas = self._canvas
        canvas.delete("all")

        # Заголовок
        canvas.create_rectangle(
            0, 0, self._total_width, self.HEADER_HEIGHT, fill=BG_HEADER, outline=""
        )
        for key, title, _width, _anchor in self.COLUMNS:
            if key in ("key", "enabled"):
                # Заголовки колонок с иконками — по центру
                canvas.create_text(
                    self._offsets[key] + self._widths[key] // 2, self.HEADER_HEIGHT // 2,
                    text=title, anchor="center", fill=FG_TEXT, font=self._bold_font
                )
                continue

            canvas.create_text(
                self._offsets[key] + 4, self.HEADER_HEIGHT // 2,
                text=title, anchor="w", fill=FG_TEXT, font=self._bold_font
            )

        # Строки
        y = self.HEADER_HEIGHT
        for index in range(self._scroll_row, len(self._rows)):
            row = self._rows[index]
            selected = row.get("name") == self._selected
            background = BG_ROW_SELECTED if selected else BG_ROW
            canvas.create_rectangle(
                0, y, self._total_width, y + self.ROW_HEIGHT, fill=background, outline=""
            )

            for key, _title, _width, anchor in self.COLUMNS:
                if key == "status":
                    self._draw_status(row, y)
                elif key == "key":
                    self._draw_key_icons(row, y)
                elif key == "enabled":
                    self._draw_toggle(row, y)
                else:
                    self._draw_cell(row, key, y, anchor)

            y += self.ROW_HEIGHT

    def _draw_cell(self, row: Dict, key: str, y: int, anchor: str):
        """Рисует обычную ячейку таблицы."""
        text = str(row.get(key, "") or "")
        x = self._offsets[key] + 4

        self._canvas.create_text(
            x, y + self.ROW_HEIGHT // 2, text=text, anchor="w",
            fill=FG_TEXT if anchor == "w" else FG_MUTED, font=self._font
        )

    def _draw_status(self, row: Dict, y: int):
        """Рисует цветную точку статуса и подпись."""
        x = self._offsets["status"] + 8
        center_y = y + self.ROW_HEIGHT // 2
        color = row.get("status_color", FG_MUTED)

        self._canvas.create_oval(
            x - 5, center_y - 5, x + 5, center_y + 5, fill=color, outline=""
        )
        self._canvas.create_text(
            x + 10, center_y, text=row.get("status_text", ""), anchor="w",
            fill=FG_MUTED, font=self._font
        )

    def _draw_key_icons(self, row: Dict, y: int):
        """Рисует иконки ключа в строке: копирование и выпуск нового ключа."""
        center_y = y + self.ROW_HEIGHT // 2
        offset = self._offsets["key"]
        has_key = row.get("has_key", False)

        self._draw_copy_icon(offset + 18, center_y, has_key)
        self._draw_refresh_icon(offset + 48, center_y, has_key)

    def _draw_copy_icon(self, center_x: int, center_y: int, enabled: bool):
        """Рисует иконку копирования API-ключа."""
        color = FG_ACCENT if enabled else FG_OFF

        # Задний лист
        self._canvas.create_rectangle(
            center_x - 1, center_y - 8, center_x + 8, center_y + 3,
            outline=color, width=1
        )
        # Передний лист
        self._canvas.create_rectangle(
            center_x - 5, center_y - 4, center_x + 4, center_y + 7,
            fill=color, outline=color
        )

    def _draw_refresh_icon(self, center_x: int, center_y: int, enabled: bool):
        """Рисует иконку «выпустить новый ключ» (круговая стрелка)."""
        color = FG_ACCENT if enabled else FG_OFF
        radius = 8
        start = 40
        extent = 280

        self._canvas.create_arc(
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius,
            start=start, extent=extent, style="arc", outline=color, width=2
        )

        # Стрелка на конце дуги
        angle = math.radians(start + extent)
        tip_x = center_x + radius * math.cos(angle)
        tip_y = center_y - radius * math.sin(angle)
        self._canvas.create_polygon(
            tip_x + 1, tip_y,
            tip_x - 6, tip_y - 3,
            tip_x - 3, tip_y + 4,
            fill=color, outline=color
        )

    def _draw_toggle(self, row: Dict, y: int):
        """Рисует переключатель вкл/выкл подключения."""
        center_x = self._offsets["enabled"] + self._widths["enabled"] // 2
        center_y = y + self.ROW_HEIGHT // 2
        enabled = row.get("enabled", True)
        track_color = FG_OK if enabled else FG_OFF
        radius = 7

        # Дорожка переключателя (скруглённая полоса)
        self._canvas.create_rectangle(
            center_x - 6, center_y - radius, center_x + 6, center_y + radius,
            fill=track_color, outline=""
        )
        self._canvas.create_oval(
            center_x - 13, center_y - radius, center_x - 6 + radius, center_y + radius,
            fill=track_color, outline=""
        )
        self._canvas.create_oval(
            center_x + 6 - radius, center_y - radius, center_x + 13, center_y + radius,
            fill=track_color, outline=""
        )

        # Кнопка переключателя
        knob_x = center_x + 7 if enabled else center_x - 7
        self._canvas.create_oval(
            knob_x - 6, center_y - 6, knob_x + 6, center_y + 6,
            fill="#f0f0f0", outline=""
        )

    # ------------------------------------------------------------------
    # События
    # ------------------------------------------------------------------

    def _row_at(self, event) -> Optional[Dict]:
        """Строка под курсором (или None)."""
        if event.y < self.HEADER_HEIGHT:
            return None

        index = self._scroll_row + (event.y - self.HEADER_HEIGHT) // self.ROW_HEIGHT

        if index < 0 or index >= len(self._rows):
            return None

        return self._rows[index]

    def _column_at(self, x: int) -> Optional[str]:
        """Колонка под курсором (или None)."""
        for key, _title, width, _anchor in self.COLUMNS:
            offset = self._offsets[key]
            if offset <= x < offset + width:
                return key
        return None

    def _on_click(self, event):
        """Клик по строке: выбор подключения или действие по иконке."""
        row = self._row_at(event)

        if row is None:
            return

        name = row.get("name", "")
        column = self._column_at(event.x)

        if column == "enabled":
            if self._on_toggle:
                self._on_toggle(name)
            return

        if column == "key":
            offset = self._offsets["key"]
            if event.x < offset + 35:
                if self._on_copy_key:
                    self._on_copy_key(name)
            elif self._on_regenerate_key:
                self._on_regenerate_key(name)
            return

        self.select(name)

        if self._on_select:
            self._on_select(name)

    def _on_mousewheel(self, event):
        """Прокрутка списка колесом мыши (по одной строке)."""
        step = -1 if event.delta > 0 else 1
        new_row = self._scroll_row + step

        if new_row == self._scroll_row:
            return

        self._scroll_row = new_row
        self._clamp_scroll()
        self._redraw()
