"""Поле (стовпець) таблиці."""

from ..datatypes import SchemaError


class Column:
    """Іменоване поле таблиці із закріпленим за ним типом даних."""

    def __init__(self, name, dtype):
        name = name.strip()
        if not name:
            raise SchemaError("Назва поля не може бути порожньою")
        self.name = name
        self.dtype = dtype

    def parse(self, raw):
        return self.dtype.parse(raw)

    def to_dict(self):
        return {"name": self.name, "type": self.dtype.name}

    @staticmethod
    def from_dict(d, reg):
        return Column(d["name"], reg.get(d["type"]))
