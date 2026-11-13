"""Таблица подключений для вкладки «Подключения».

Таблица нарисована на Canvas: так статус подключения показывается цветной точкой
в отдельной ячейке, а рядом с каждой строкой стоит иконка копирования API-ключа.
В ttk.Treeview цвет задаётся для всей строки, отдельную ячейку покрасить нельзя.
"""
import logging
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


class ConnectionTable(ctk.CTkFrame):
    """Список подключений: имя, хост, порт, база, пользователь, статус, ключ."""

    # (ключ, заголовок, ширина, выравнивание)
    COLUMNS = (
        ("name", "Имя", 140, "w"),
        ("host", "Хост", 105, "w"),
        ("port", "Порт", 45, "w"),
        ("db", "База", 80, "w"),
        ("user", "Пользователь", 110, "w"),
        ("status", "Статус", 90, "w"),
        ("key", "Ключ", 45, "center"),
    )

    ROW_HEIGHT = 24
    HEADER_HEIGHT = 22

    def __init__(self, master, visible_rows: int = 4,
                 on_select: Optional[Callable[[str], None]] = None,
                 on_copy_key: Optional[Callable[[str], None]] = None):
        """Создаёт таблицу подключений.

        Args:
            master: Родительский виджет
            visible_rows: Сколько строк видно без прокрутки
            on_select: Обработчик выбора строки (имя подключения)
            on_copy_key: Обработчик клика по иконке ключа (имя подключения)
        """
        super().__init__(master, fg_color="transparent")

        self._rows: List[Dict] = []
        self._selected: Optional[str] = None
        self._scroll_row = 0
        self._on_select = on_select
        self._on_copy_key = on_copy_key

        self._font = tkfont.Font(family="Segoe UI", size=10)
        self._bold_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")

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
                status_color, status_text, has_key, is_default
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
            if key == "key":
                # Заголовок колонки ключа — по центру, над иконкой
                canvas.create_text(
                    self._offsets[key] + 22, self.HEADER_HEIGHT // 2,
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
                    self._draw_key_icon(row, y)
                else:
                    self._draw_cell(row, key, y, anchor)

            y += self.ROW_HEIGHT

    def _draw_cell(self, row: Dict, key: str, y: int, anchor: str):
        """Рисует обычную ячейку таблицы."""
        text = str(row.get(key, "") or "")
        x = self._offsets[key] + 4

        if key == "name" and row.get("is_default"):
            text = f"\u2605 {text}"
            self._canvas.create_text(
                x, y + self.ROW_HEIGHT // 2, text=text, anchor="w",
                fill=FG_TEXT, font=self._bold_font
            )
            return

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

    def _draw_key_icon(self, row: Dict, y: int):
        """Рисует иконку копирования API-ключа в строке."""
        center_x = self._offsets["key"] + 22
        center_y = y + self.ROW_HEIGHT // 2
        color = FG_ACCENT if row.get("has_key") else "#5a5a5a"

        # Задний лист
        self._canvas.create_rectangle(
            center_x - 2, center_y - 7, center_x + 7, center_y + 4,
            outline=color, width=1
        )
        # Передний лист
        self._canvas.create_rectangle(
            center_x - 6, center_y - 3, center_x + 3, center_y + 8,
            fill=color, outline=color
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

    def _is_key_column(self, x: int) -> bool:
        """Курсор в колонке «Ключ»."""
        offset = self._offsets["key"]
        return offset <= x <= offset + self._widths["key"]

    def _on_click(self, event):
        """Клик по строке: выбор подключения или копирование ключа."""
        row = self._row_at(event)

        if row is None:
            return

        name = row.get("name", "")

        if self._is_key_column(event.x):
            if self._on_copy_key:
                self._on_copy_key(name)
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
