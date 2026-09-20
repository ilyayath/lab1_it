"""Головне вікно застосунку TabDB."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..datatypes import TabDBError
from ..service import DatabaseService
from .dialogs import (
    IntersectionDialog,
    NameDialog,
    RowEditorDialog,
    ServerDatabaseDialog,
    TableCreationDialog,
)
from .table_view import TableView

APP_TITLE = "TabDB — система керування табличними базами даних"


class MainWindow(tk.Tk):
    """Меню, список таблиць, перегляд рядків, рядок стану.

    Реалізує життєвий цикл бази з діаграми станів: «немає бази» →
    «змінена» ↔ «синхронізована з файлом», із підтвердженням закриття
    зміненої бази.

    service — локальний DatabaseService або RemoteDatabaseService; у другому
    випадку «Відкрити» показує бази сервера, а «Зберегти як» експортує
    копію бази в локальний файл.
    """

    def __init__(self, service=None):
        super().__init__()
        self.service = service or DatabaseService()

        self.geometry("1200x660")
        self.minsize(1000, 520)

        self.build_menu()
        self.build_layout()
        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.refresh()

    # --- побудова інтерфейсу ---

    def build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Створити базу…", accelerator="Ctrl+N", command=self.on_new_db)
        file_menu.add_command(label="Відкрити базу…", accelerator="Ctrl+O", command=self.on_open_db)
        if self.service.is_remote:
            file_menu.add_command(label="Імпортувати файл на сервер…", command=self.on_import_db)
        file_menu.add_separator()
        file_menu.add_command(label="Зберегти", accelerator="Ctrl+S", command=self.on_save_db)
        file_menu.add_command(
            label="Експортувати у файл…" if self.service.is_remote else "Зберегти як…",
            command=self.on_save_db_as)
        file_menu.add_separator()
        file_menu.add_command(label="Закрити базу", command=self.on_close_db)
        file_menu.add_command(label="Вихід", command=self.on_exit)
        menubar.add_cascade(label="Файл", menu=file_menu)

        table_menu = tk.Menu(menubar, tearoff=False)
        table_menu.add_command(label="Створити таблицю…", command=self.on_create_table)
        table_menu.add_command(label="Видалити таблицю", command=self.on_drop_table)
        menubar.add_cascade(label="Таблиця", menu=table_menu)

        row_menu = tk.Menu(menubar, tearoff=False)
        row_menu.add_command(label="Додати рядок…", command=self.on_add_row)
        row_menu.add_command(label="Редагувати рядок…", command=self.on_edit_row)
        row_menu.add_command(label="Видалити рядок", command=self.on_delete_row)
        menubar.add_cascade(label="Рядок", menu=row_menu)

        ops_menu = tk.Menu(menubar, tearoff=False)
        ops_menu.add_command(label="Перетин таблиць…", command=self.on_intersect)
        menubar.add_cascade(label="Операції", menu=ops_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Про програму", command=self.on_about)
        menubar.add_cascade(label="Довідка", menu=help_menu)

        self.config(menu=menubar)
        self.bind("<Control-n>", lambda e: self.on_new_db())
        self.bind("<Control-o>", lambda e: self.on_open_db())
        self.bind("<Control-s>", lambda e: self.on_save_db())

    def build_layout(self):
        toolbar = ttk.Frame(self, padding=(8, 6))
        toolbar.pack(fill="x")
        buttons = [
            ("Нова база", self.on_new_db),
            ("Відкрити", self.on_open_db),
            ("Зберегти", self.on_save_db),
            None,
            ("Створити таблицю", self.on_create_table),
            ("Видалити таблицю", self.on_drop_table),
            None,
            ("Додати рядок", self.on_add_row),
            ("Редагувати", self.on_edit_row),
            ("Видалити рядок", self.on_delete_row),
        ]
        for item in buttons:
            if item is None:
                ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
            else:
                text, command = item
                ttk.Button(toolbar, text=text, command=command).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Перетин таблиць", command=self.on_intersect).pack(side="right")

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        left = ttk.Frame(paned, padding=(0, 0, 6, 0))
        ttk.Label(left, text="Таблиці бази", font=("", 10, "bold")).pack(anchor="w", pady=(0, 4))
        self.lst_tables = tk.Listbox(left, exportselection=False, activestyle="none")
        self.lst_tables.pack(fill="both", expand=True)
        self.lst_tables.bind("<<ListboxSelect>>", lambda e: self.on_select_table())
        paned.add(left, weight=1)

        right = ttk.Frame(paned)
        self.lbl_schema = ttk.Label(right, text="", foreground="#34495E")
        self.lbl_schema.pack(anchor="w", pady=(0, 4))
        self.view = TableView(right)
        self.view.pack(fill="both", expand=True)
        self.view.bind_double_click(lambda e: self.on_edit_row())
        paned.add(right, weight=4)

        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, relief="sunken",
                  anchor="w", padding=(8, 3)).pack(fill="x", side="bottom")

    # --- оновлення інтерфейсу ---

    def refresh(self, select=None):
        """Перемальовує заголовок, список таблиць і поточну таблицю."""
        target = select or self.current_table_name()
        self.lst_tables.delete(0, tk.END)
        names = self.service.table_names()
        for name in names:
            self.lst_tables.insert(tk.END, name)

        if target in names:
            index = names.index(target)
            self.lst_tables.selection_set(index)
            self.lst_tables.see(index)
        elif names:
            self.lst_tables.selection_set(0)

        self.update_title()
        self.on_select_table()

    def update_title(self):
        if not self.service.has_db():
            self.title(APP_TITLE)
            return
        mark = "*" if self.service.is_modified() else ""
        self.title(f"{mark}{self.service.db_name()} [{self.service.location()}] — {APP_TITLE}")

    def current_table_name(self):
        selection = self.lst_tables.curselection()
        return self.lst_tables.get(selection[0]) if selection else None

    def on_select_table(self):
        """UC-06: показати рядки обраної таблиці."""
        name = self.current_table_name()
        if not self.service.has_db() or name is None:
            self.view.clear()
            self.lbl_schema.configure(text="")
            self.status.set("База даних не відкрита" if not self.service.has_db() else "Таблиць немає")
            return

        table = self.service.get_table(name)
        self.view.show(table)
        schema = ", ".join(f"{field}: {type_name}" for field, type_name in table.schema())
        self.lbl_schema.configure(text=f"Схема «{table.name}» — {schema}")
        self.status.set(
            f"Таблиця «{table.name}»: полів {len(table.columns)}, рядків {table.row_count()}")

    # --- сценарії з базою ---

    def on_new_db(self):
        """UC-01."""
        if not self.confirm_discard():
            return
        name = NameDialog(self, "Нова база даних", "Назва бази даних:").show()
        if not name:
            return
        try:
            self.service.create_database(name)
        except TabDBError as exc:
            self.show_error(exc)
            return
        self.refresh()
        self.status.set(f"Створено базу даних «{name}»")

    def on_open_db(self):
        """UC-02."""
        if not self.confirm_discard():
            return
        if self.service.is_remote:
            try:
                databases = self.service.list_databases()
            except TabDBError as exc:
                self.show_error(exc)
                return
            target = ServerDatabaseDialog(self, databases).show()
        else:
            target = filedialog.askopenfilename(
                title="Відкрити базу даних",
                filetypes=list(self.service.storage.file_types),
                parent=self,
            )
        if not target:
            return
        try:
            self.service.open_database(target)
        except TabDBError as exc:
            self.show_error(exc)
            return
        self.refresh()
        self.status.set(f"Відкрито «{self.service.db_name()}»: "
                        f"таблиць {len(self.service.table_names())}")

    def on_import_db(self):
        """Завантажує локальний файл бази на сервер і відкриває його."""
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Імпортувати базу даних на сервер",
            filetypes=list(self.service.storage.file_types),
            parent=self,
        )
        if not path:
            return
        try:
            self.service.import_database(path)
        except TabDBError as exc:
            self.show_error(exc)
            return
        self.refresh()
        self.status.set(f"Базу «{self.service.db_name()}» імпортовано на сервер")

    def on_save_db(self):
        """UC-03. Повертає True, якщо базу збережено."""
        if not self.service.has_db():
            self.warn("Немає відкритої бази даних")
            return False
        if not self.service.is_remote and self.service.path is None:
            return self.on_save_db_as()
        return self.save_to(None)

    def on_save_db_as(self):
        """Локально — «Зберегти як», для сервера — експорт копії у файл."""
        if not self.service.has_db():
            self.warn("Немає відкритої бази даних")
            return False
        extension = self.service.storage.extension
        path = filedialog.asksaveasfilename(
            title="Експортувати базу даних" if self.service.is_remote else "Зберегти базу даних як",
            initialfile=self.service.db_name() + extension,
            defaultextension=extension,
            filetypes=list(self.service.storage.file_types),
            parent=self,
        )
        if not path:
            return False
        if self.service.is_remote:
            try:
                self.service.export_database(path)
            except TabDBError as exc:
                self.show_error(exc)
                return False
            self.status.set(f"Копію бази експортовано у «{path}»")
            return True
        return self.save_to(Path(path))

    def save_to(self, path):
        try:
            saved = self.service.save_database(path)
        except TabDBError as exc:
            self.show_error(exc)
            return False
        self.update_title()
        self.status.set(f"Базу збережено: {saved}")
        return True

    def on_close_db(self):
        if not self.service.has_db():
            return
        if not self.confirm_discard():
            return
        self.service.close_database()
        self.refresh()
        self.status.set("Базу даних закрито")

    def on_exit(self):
        if self.confirm_discard():
            self.destroy()

    def confirm_discard(self):
        """Питає про незбережені зміни перед закриттям бази."""
        if not self.service.is_modified():
            return True
        answer = messagebox.askyesnocancel(
            "Незбережені зміни",
            "База даних містить незбережені зміни. Зберегти їх?",
            parent=self,
        )
        if answer is None:
            return False
        if not answer:
            self.service.discard_changes()
            self.refresh()
            return True
        return self.on_save_db()

    # --- сценарії з таблицями ---

    def on_create_table(self):
        """UC-04."""
        if not self.require_db():
            return
        table = TableCreationDialog(self, self.service).show()
        if table is not None:
            self.refresh(select=table.name)
            self.status.set(f"Створено таблицю «{table.name}»")

    def on_drop_table(self):
        """UC-05."""
        name = self.require_table_name()
        if name is None:
            return
        if not messagebox.askyesno("Видалення таблиці",
                                   f"Видалити таблицю «{name}» разом із усіма рядками?",
                                   parent=self):
            return
        self.service.drop_table(name)
        self.refresh()
        self.status.set(f"Таблицю «{name}» видалено")

    # --- сценарії з рядками ---

    def on_add_row(self):
        """UC-07."""
        name = self.require_table_name()
        if name is None:
            return
        table = self.service.get_table(name)
        if RowEditorDialog(self, self.service, table).show() is not None:
            self.refresh(select=name)
            self.view.select_index(self.view.table.row_count() - 1)
            self.status.set(f"До таблиці «{name}» додано рядок")

    def on_edit_row(self):
        """UC-08."""
        name = self.require_table_name()
        if name is None:
            return
        index = self.view.selected_index()
        if index is None:
            self.warn("Оберіть рядок для редагування")
            return
        table = self.service.get_table(name)
        if RowEditorDialog(self, self.service, table, index).show() is not None:
            self.refresh(select=name)
            self.view.select_index(index)
            self.status.set(f"Рядок №{index + 1} оновлено")

    def on_delete_row(self):
        """UC-09."""
        name = self.require_table_name()
        if name is None:
            return
        index = self.view.selected_index()
        if index is None:
            self.warn("Оберіть рядок для видалення")
            return
        if not messagebox.askyesno("Видалення рядка", f"Видалити рядок №{index + 1}?",
                                   parent=self):
            return
        self.service.delete_row(name, index)
        self.refresh(select=name)
        self.status.set(f"Рядок №{index + 1} видалено")

    # --- операції ---

    def on_intersect(self):
        """UC-10."""
        if not self.require_db():
            return
        if len(self.service.table_names()) < 2:
            self.warn("Для перетину потрібні щонайменше дві таблиці в базі")
            return

        outcome = IntersectionDialog(self, self.service, self.current_table_name()).show()
        if outcome is None:
            return
        result, saved = outcome
        self.refresh(select=result.name if saved else self.current_table_name())
        suffix = " і збережено в базі" if saved else " (без збереження в базі)"
        self.status.set(f"Перетин виконано: у «{result.name}» {result.row_count()} рядків{suffix}")

    def on_about(self):
        mode = ("клієнт, " + self.service.location()) if self.service.is_remote else "локальний"
        messagebox.showinfo(
            "Про програму",
            "TabDB — часткова реалізація системи керування табличними базами даних.\n\n"
            "Типи полів: integer, real, char, string, complexInteger, complexReal.\n"
            "Додаткова операція над таблицями: перетин.\n"
            "Формат збереження: JSON (*.tdb.json).\n"
            f"Режим: {mode}.",
            parent=self,
        )

    # --- допоміжні ---

    def require_db(self):
        if not self.service.has_db():
            self.warn("Спочатку створіть або відкрийте базу даних")
            return False
        return True

    def require_table_name(self):
        if not self.require_db():
            return None
        name = self.current_table_name()
        if name is None:
            self.warn("Оберіть таблицю у списку зліва")
            return None
        return name

    def warn(self, message):
        messagebox.showwarning("TabDB", message, parent=self)
        self.status.set(message)

    def report_callback_exception(self, exc_type, exc, tb):
        """Помилки застосунку (зокрема мережеві) показує діалогом, а не в консолі."""
        if isinstance(exc, TabDBError):
            self.show_error(exc)
        else:
            super().report_callback_exception(exc_type, exc, tb)

    def show_error(self, exc):
        messagebox.showerror("Помилка", str(exc), parent=self)
        self.status.set(str(exc))
