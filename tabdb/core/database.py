"""База даних — контейнер таблиць."""

from ..datatypes import NotFoundError, SchemaError
from .table import Table


class Database:
    """Іменований набір таблиць без реляцій між ними.

    Прапорець modified відповідає станам «Змінена» та «Синхронізована
    з файлом» із діаграми станів.
    """

    def __init__(self, name):
        name = name.strip()
        if not name:
            raise SchemaError("Назва бази даних не може бути порожньою")
        self.name = name
        self.tables = {}
        self.modified = False

    def create_table(self, name, columns):
        table = Table(name, columns)
        self.add_table(table)
        return table

    def add_table(self, table):
        if table.name in self.tables:
            raise SchemaError(f"Таблиця «{table.name}» уже існує в базі «{self.name}»")
        self.tables[table.name] = table
        self.mark_modified()

    def drop_table(self, name):
        if name not in self.tables:
            raise NotFoundError(f"Таблиці «{name}» немає в базі «{self.name}»")
        del self.tables[name]
        self.mark_modified()

    def get_table(self, name):
        if name not in self.tables:
            raise NotFoundError(f"Таблиці «{name}» немає в базі «{self.name}»")
        return self.tables[name]

    def has_table(self, name):
        return name in self.tables

    def table_names(self):
        return list(self.tables)

    def mark_modified(self):
        self.modified = True

    def mark_saved(self):
        self.modified = False

    def is_modified(self):
        return self.modified

    def to_dict(self):
        return {
            "format": "tabdb",
            "version": 1,
            "name": self.name,
            "tables": [table.to_dict() for table in self.tables.values()],
        }

    @staticmethod
    def from_dict(d, reg):
        if not isinstance(d, dict) or "name" not in d:
            raise SchemaError("Файл не містить опису бази даних TabDB")
        db = Database(d["name"])
        for raw_table in d["tables"]:
            db.add_table(Table.from_dict(raw_table, reg))
        db.mark_saved()
        return db
