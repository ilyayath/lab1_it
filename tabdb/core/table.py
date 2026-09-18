"""Таблиця бази даних."""

from ..datatypes import NotFoundError, SchemaError, ValidationError
from .column import Column
from .row import Row


class Table:
    """Таблиця: іменована схема полів і список рядків.

    Кількість полів і рядків не обмежена. Кожен рядок перед додаванням
    проходить валідацію за типами полів.
    """

    def __init__(self, name, columns, rows=None):
        name = name.strip()
        if not name:
            raise SchemaError("Назва таблиці не може бути порожньою")
        if not columns:
            raise SchemaError(f"Таблиця «{name}» повинна мати хоча б одне поле")

        seen = set()
        for col in columns:
            if col.name in seen:
                raise SchemaError(f"Поле «{col.name}» оголошено двічі")
            seen.add(col.name)

        self.name = name
        self.columns = list(columns)
        self.rows = list(rows or [])

    def schema(self):
        """Схема таблиці як список пар «назва поля, назва типу»."""
        return [(col.name, col.dtype.name) for col in self.columns]

    def is_compatible(self, other):
        """Чи однакові схеми таблиць."""
        return self.schema() == other.schema()

    def validate_row(self, raw):
        """Перевіряє та перетворює текстові значення рядка.

        Помилки збираються з усіх полів одразу, щоб GUI міг підсвітити їх разом.
        """
        if len(raw) != len(self.columns):
            raise ValidationError(
                f"Очікується {len(self.columns)} значень, отримано {len(raw)}"
            )

        values = []
        errors = {}
        for index, (col, text) in enumerate(zip(self.columns, raw)):
            try:
                values.append(col.parse(text))
            except ValidationError as exc:
                errors[index] = str(exc)
                values.append(None)

        if errors:
            details = "; ".join(
                f"«{self.columns[i].name}»: {msg}" for i, msg in errors.items()
            )
            raise ValidationError(f"Помилки валідації рядка: {details}", errors)
        return values

    def add_row(self, raw):
        row = Row(self.validate_row(raw))
        self.rows.append(row)
        return row

    def append_row(self, row):
        """Додає вже валідний рядок (використовують операція перетину та сховище)."""
        self.rows.append(row)

    def update_row(self, index, raw):
        self.check_index(index)
        row = Row(self.validate_row(raw))
        self.rows[index] = row
        return row

    def delete_row(self, index):
        self.check_index(index)
        del self.rows[index]

    def check_index(self, index):
        if not 0 <= index < len(self.rows):
            raise NotFoundError(f"У таблиці «{self.name}» немає рядка №{index + 1}")

    def get_rows(self):
        return self.rows

    def row_count(self):
        return len(self.rows)

    def formatted_row(self, index):
        """Значення рядка у вигляді тексту — для показу й редагування у GUI."""
        row = self.rows[index]
        return [col.dtype.format(value) for col, value in zip(self.columns, row.values)]

    def to_dict(self):
        return {
            "name": self.name,
            "columns": [col.to_dict() for col in self.columns],
            "rows": [
                [col.dtype.to_json(value) for col, value in zip(self.columns, row.values)]
                for row in self.rows
            ],
        }

    @staticmethod
    def from_dict(d, reg):
        columns = [Column.from_dict(c, reg) for c in d["columns"]]
        table = Table(d["name"], columns)
        for raw_row in d["rows"]:
            if len(raw_row) != len(columns):
                raise SchemaError(f"Таблиця «{table.name}»: некоректна кількість значень у рядку")
            table.rows.append(
                Row([col.dtype.from_json(item) for col, item in zip(columns, raw_row)])
            )
        return table
