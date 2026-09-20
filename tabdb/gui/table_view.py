"""Показ вмісту таблиці."""

from tkinter import ttk


class TableView(ttk.Frame):
    """Таблиця на базі ttk.Treeview зі смугами прокручування.

    Номер рядка в дереві збігається з його індексом у Table.rows, тому
    виділення напряму відображається на індекс для редагування.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.table = None

        self.tree = ttk.Treeview(self, show="headings", selectmode="browse")
        y_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree.tag_configure("odd", background="#F5F8FC")

    def show(self, table):
        """Перемальовує вміст таблиці (UC-06)."""
        self.table = table
        self.tree.delete(*self.tree.get_children())

        if table is None:
            self.tree["columns"] = ()
            return

        column_ids = [f"c{i}" for i in range(len(table.columns))]
        self.tree["columns"] = column_ids
        for column_id, col in zip(column_ids, table.columns):
            self.tree.heading(column_id, text=f"{col.name} : {col.dtype.name}")
            self.tree.column(column_id, width=140, minwidth=70, anchor="w")

        for index in range(table.row_count()):
            self.tree.insert(
                "", "end", iid=str(index),
                values=table.formatted_row(index),
                tags=("odd" if index % 2 else "even",),
            )

    def clear(self):
        self.show(None)

    def selected_index(self):
        """Індекс виділеного рядка або None, якщо нічого не виділено."""
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def select_index(self, index):
        item = str(index)
        if self.tree.exists(item):
            self.tree.selection_set(item)
            self.tree.focus(item)
            self.tree.see(item)

    def bind_double_click(self, callback):
        self.tree.bind("<Double-1>", callback)
