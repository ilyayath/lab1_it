"""Діалоги: створення таблиці, редактор рядка, перетин таблиць."""

import tkinter as tk
from tkinter import messagebox, ttk

from ..datatypes import TabDBError, ValidationError
from .table_view import TableView

ERROR_COLOR = "#C0392B"
HINT_COLOR = "#7F8C8D"


class ModalDialog(tk.Toplevel):
    """Основа модальних вікон: кнопки «ОК»/«Скасувати», центрування."""

    def __init__(self, master, title):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.transient(master)
        self.result = None

        self.body = ttk.Frame(self, padding=12)
        self.body.pack(fill="both", expand=True)

        self.buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        self.buttons.pack(fill="x")
        ttk.Button(self.buttons, text="Скасувати", command=self.on_cancel).pack(side="right")
        self.ok_button = ttk.Button(self.buttons, text="ОК", command=self.on_ok)
        self.ok_button.pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda e: self.on_cancel())
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def show(self):
        """Показує вікно модально й повертає self.result."""
        self.update_idletasks()
        self.center()
        self.grab_set()
        self.wait_window(self)
        return self.result

    def center(self):
        master = self.master
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def on_ok(self):
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

    def show_error(self, msg):
        messagebox.showerror("Помилка", msg, parent=self)


class NameDialog(ModalDialog):
    """UC-01: запит назви для нової бази даних."""

    def __init__(self, master, title, prompt):
        super().__init__(master, title)
        ttk.Label(self.body, text=prompt).pack(anchor="w")
        self.var_name = tk.StringVar()
        entry = ttk.Entry(self.body, textvariable=self.var_name, width=32)
        entry.pack(fill="x", pady=(6, 0))
        entry.focus_set()
        self.bind("<Return>", lambda e: self.on_ok())

    def on_ok(self):
        name = self.var_name.get().strip()
        if not name:
            self.show_error("Вкажіть назву")
            return
        self.result = name
        self.destroy()


class TableCreationDialog(ModalDialog):
    """UC-04: назва таблиці та довільна кількість полів із типами."""

    def __init__(self, master, service):
        super().__init__(master, "Створення таблиці")
        self.service = service
        self.type_names = service.registry.names()
        self.field_rows = []

        name_frame = ttk.Frame(self.body)
        name_frame.pack(fill="x")
        ttk.Label(name_frame, text="Назва таблиці:").pack(side="left")
        self.var_name = tk.StringVar()
        entry = ttk.Entry(name_frame, textvariable=self.var_name, width=28)
        entry.pack(side="left", padx=(8, 0))
        entry.focus_set()

        ttk.Separator(self.body).pack(fill="x", pady=10)
        header = ttk.Frame(self.body)
        header.pack(fill="x")
        ttk.Label(header, text="Поля таблиці", font=("", 9, "bold")).pack(side="left")
        ttk.Button(header, text="+ Додати поле", command=self.add_field).pack(side="right")

        self.fields_frame = ttk.Frame(self.body)
        self.fields_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.add_field()

    def add_field(self):
        row = ttk.Frame(self.fields_frame)
        row.pack(fill="x", pady=2)

        var_name = tk.StringVar()
        var_type = tk.StringVar(value=self.type_names[0])

        ttk.Label(row, text=f"{len(self.field_rows) + 1}.", width=3).pack(side="left")
        ttk.Entry(row, textvariable=var_name, width=20).pack(side="left")
        ttk.Combobox(row, textvariable=var_type, values=self.type_names,
                     state="readonly", width=16).pack(side="left", padx=6)
        ttk.Button(row, text="X", width=3, command=lambda: self.remove_field(row)).pack(side="left")

        self.field_rows.append((row, var_name, var_type))

    def remove_field(self, row):
        if len(self.field_rows) <= 1:
            self.show_error("Таблиця повинна мати хоча б одне поле")
            return
        self.field_rows = [item for item in self.field_rows if item[0] is not row]
        row.destroy()
        # Перенумерувати поля, що залишилися.
        for number, (frame, _, _) in enumerate(self.field_rows, start=1):
            frame.winfo_children()[0].configure(text=f"{number}.")

    def on_ok(self):
        name = self.var_name.get().strip()
        specs = [(var_name.get().strip(), var_type.get())
                 for _, var_name, var_type in self.field_rows]

        if not name:
            self.show_error("Вкажіть назву таблиці")
            return
        if any(not field for field, _ in specs):
            self.show_error("Кожне поле повинно мати назву")
            return

        try:
            self.result = self.service.create_table(name, specs)
        except TabDBError as exc:
            self.show_error(str(exc))
            return
        self.destroy()


class RowEditorDialog(ModalDialog):
    """UC-07 / UC-08: введення або редагування значень рядка.

    За ValidationError підсвічує ті поля, які не пройшли валідацію.
    """

    def __init__(self, master, service, table, index=None):
        title = "Додавання рядка" if index is None else f"Редагування рядка №{index + 1}"
        super().__init__(master, title)
        self.service = service
        self.table = table
        self.index = index
        self.entries = []
        self.hints = []

        grid = ttk.Frame(self.body)
        grid.pack(fill="both", expand=True)
        for column, text in enumerate(("Поле", "Значення", "Формат")):
            ttk.Label(grid, text=text, font=("", 9, "bold")).grid(
                row=0, column=column, sticky="w", padx=(10, 0) if column else 0)

        if index is None:
            current = [""] * len(table.columns)
        else:
            current = table.formatted_row(index)

        for number, (col, value) in enumerate(zip(table.columns, current), start=1):
            ttk.Label(grid, text=f"{col.name} : {col.dtype.name}").grid(
                row=number, column=0, sticky="w", pady=3)
            entry = ttk.Entry(grid, width=28)
            entry.insert(0, value)
            entry.grid(row=number, column=1, sticky="ew", padx=(10, 0), pady=3)
            entry.bind("<KeyRelease>", lambda e, i=number - 1: self.reset_hint(i))
            hint = ttk.Label(grid, text=col.dtype.hint, foreground=HINT_COLOR)
            hint.grid(row=number, column=2, sticky="w", padx=(10, 0), pady=3)
            self.entries.append(entry)
            self.hints.append(hint)

        grid.columnconfigure(1, weight=1)
        self.entries[0].focus_set()
        self.bind("<Return>", lambda e: self.on_ok())

    def collect_values(self):
        return [entry.get() for entry in self.entries]

    def reset_hint(self, index):
        """Повертає підказку про формат, щойно користувач змінює значення."""
        hint = self.table.columns[index].dtype.hint
        self.hints[index].configure(text=hint, foreground=HINT_COLOR)

    def highlight_errors(self, errors):
        """Замінює підказку про формат на текст помилки для хибних полів."""
        for position, (col, hint) in enumerate(zip(self.table.columns, self.hints)):
            if position in errors:
                hint.configure(text=errors[position], foreground=ERROR_COLOR)
            else:
                hint.configure(text=col.dtype.hint, foreground=HINT_COLOR)
        if errors:
            self.entries[min(errors)].focus_set()

    def on_ok(self):
        raw = self.collect_values()
        try:
            if self.index is None:
                self.result = self.service.add_row(self.table.name, raw)
            else:
                self.result = self.service.update_row(self.table.name, self.index, raw)
        except ValidationError as exc:
            self.highlight_errors(exc.errors)
            if not exc.errors:
                self.show_error(str(exc))
            return
        except TabDBError as exc:
            self.show_error(str(exc))
            return
        self.destroy()


class IntersectionDialog(ModalDialog):
    """UC-10: вибір двох таблиць, назви результату та режиму збереження."""

    def __init__(self, master, service, preselected=None):
        super().__init__(master, "Перетин таблиць")
        self.service = service
        names = service.table_names()
        self.suggested = ""

        grid = ttk.Frame(self.body)
        grid.pack(fill="both", expand=True)

        self.var_first = tk.StringVar(value=preselected or names[0])
        self.var_second = tk.StringVar(value=names[1] if len(names) > 1 else "")
        self.var_result = tk.StringVar()
        self.var_save = tk.BooleanVar(value=True)

        ttk.Label(grid, text="Перша таблиця (A):").grid(row=0, column=0, sticky="w", pady=4)
        self.cb_first = ttk.Combobox(grid, textvariable=self.var_first, values=names,
                                     state="readonly", width=24)
        self.cb_first.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        ttk.Label(grid, text="Друга таблиця (B):").grid(row=1, column=0, sticky="w", pady=4)
        self.cb_second = ttk.Combobox(grid, textvariable=self.var_second, values=names,
                                      state="readonly", width=24)
        self.cb_second.grid(row=1, column=1, sticky="ew", padx=(10, 0))

        ttk.Label(grid, text="Назва результату:").grid(row=2, column=0, sticky="w", pady=4)
        self.ed_result = ttk.Entry(grid, textvariable=self.var_result, width=26)
        self.ed_result.grid(row=2, column=1, sticky="ew", padx=(10, 0))

        self.chk_save = ttk.Checkbutton(
            grid, text="Зберегти результат у базі як нову таблицю", variable=self.var_save)
        self.chk_save.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Label(grid, text="Схеми таблиць мають збігатися: назви, типи та порядок полів.",
                  foreground=HINT_COLOR, wraplength=340).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        grid.columnconfigure(1, weight=1)
        self.var_first.trace_add("write", self.suggest_name)
        self.var_second.trace_add("write", self.suggest_name)
        self.suggest_name()
        self.ok_button.configure(text="Виконати")

    def suggest_name(self, *args):
        """Підставляє назву «A_x_B», доки користувач не ввів власну."""
        suggestion = f"{self.var_first.get()}_x_{self.var_second.get()}"
        if not self.var_result.get() or self.var_result.get() == self.suggested:
            self.var_result.set(suggestion)
            self.suggested = suggestion

    def selected(self):
        return (self.var_first.get(), self.var_second.get(),
                self.var_result.get().strip(), self.var_save.get())

    def on_ok(self):
        first, second, result_name, save = self.selected()
        if not first or not second:
            self.show_error("Оберіть обидві таблиці")
            return
        if not result_name:
            self.show_error("Вкажіть назву таблиці-результату")
            return

        try:
            result = self.service.intersect_tables(first, second, result_name, save)
        except TabDBError as exc:
            self.show_error(str(exc))
            return

        self.result = (result, save)
        parent = self.master
        self.destroy()
        ResultWindow(parent, result)


class ResultWindow(tk.Toplevel):
    """Вікно перегляду таблиці-результату операції."""

    def __init__(self, master, table):
        super().__init__(master)
        self.title(f"Результат: {table.name}")
        self.geometry("720x420")
        self.transient(master)

        ttk.Label(self, text=f"Таблиця «{table.name}» — рядків: {table.row_count()}",
                  padding=(10, 8), font=("", 10, "bold")).pack(anchor="w")

        view = TableView(self, padding=(10, 0, 10, 10))
        view.pack(fill="both", expand=True)
        view.show(table)

        ttk.Button(self, text="Закрити", command=self.destroy).pack(pady=(0, 10))


class ServerDatabaseDialog(ModalDialog):
    """Вибір бази даних на сервері; результат — її ідентифікатор."""

    def __init__(self, master, databases):
        super().__init__(master, "Бази даних на сервері")
        self.resizable(True, True)

        if not databases:
            ttk.Label(self.body, text="На сервері ще немає баз даних.\n"
                                      "Створіть нову або імпортуйте файл.",
                      foreground=HINT_COLOR).pack(anchor="w")
            self.ok_button.configure(state="disabled")
            return

        self.tree = ttk.Treeview(self.body, columns=("name", "tables", "id"),
                                 show="headings", selectmode="browse", height=10)
        for column, text, width in (("name", "Назва", 220), ("tables", "Таблиць", 70),
                                    ("id", "Ідентифікатор", 120)):
            self.tree.heading(column, text=text)
            self.tree.column(column, width=width, anchor="w")
        for db in databases:
            self.tree.insert("", "end", iid=db["id"],
                             values=(db["name"], len(db["tables"]), db["id"]))
        self.tree.pack(fill="both", expand=True)
        self.tree.selection_set(databases[0]["id"])
        self.tree.focus_set()
        self.tree.bind("<Double-1>", lambda e: self.on_ok())
        self.bind("<Return>", lambda e: self.on_ok())
        self.ok_button.configure(text="Відкрити")

    def on_ok(self):
        selection = self.tree.selection()
        if not selection:
            self.show_error("Оберіть базу даних")
            return
        self.result = selection[0]
        self.destroy()
