"""Сховище у форматі JSON (файли *.tdb.json)."""

import json
from pathlib import Path

from ..core import Database
from ..datatypes import SchemaError, StorageError, TypeRegistry, ValidationError
from .base import StorageProvider


class JsonStorage(StorageProvider):
    """Кожна база даних зберігається в окремому JSON-файлі у кодуванні UTF-8."""

    extension = ".tdb.json"
    file_types = (("База даних TabDB", "*.tdb.json"), ("Усі файли", "*.*"))

    def __init__(self, registry=None):
        self.registry = registry or TypeRegistry.default()

    def save(self, db, path):
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(db.to_dict(), file, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise StorageError(f"Не вдалося зберегти базу у «{path}»: {exc}")

    def load(self, path):
        path = Path(path)
        try:
            with open(path, encoding="utf-8") as file:
                data = json.load(file)
        except OSError as exc:
            raise StorageError(f"Не вдалося прочитати файл «{path}»: {exc}")
        except json.JSONDecodeError as exc:
            raise StorageError(f"Файл «{path.name}» не є коректним JSON: {exc.msg}")

        try:
            return Database.from_dict(data, self.registry)
        except (SchemaError, ValidationError, KeyError, TypeError, ValueError) as exc:
            raise StorageError(f"Файл «{path.name}» має невідповідний формат: {exc}")
