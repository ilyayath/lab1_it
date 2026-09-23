"""Фасад, що працює з базою даних на сервері TabDB."""

import json
from urllib.parse import urlparse

from ..core import Table
from ..datatypes import SchemaError, StorageError, TypeRegistry
from ..storage import JsonStorage


class RemoteDatabaseService:
    """Той самий інтерфейс, що й DatabaseService, але над REST API.

    Стан бази зберігається на сервері; клієнт пам'ятає лише ідентифікатор
    відкритої бази. Таблиці приходять у форматі *.tdb.json і
    відтворюються локальними доменними об'єктами Table, тож GUI показує їх
    так само, як у локальному режимі.
    """

    is_remote = True

    def __init__(self, client, registry=None):
        self.client = client
        self.registry = registry or TypeRegistry.default()
        self.storage = JsonStorage(self.registry)
        self.db_id = None
        self.summary = None

    # --- база даних ---

    def list_databases(self):
        """Бази сервера: список словників {id, name, modified, tables}."""
        return self.client.get("databases")

    def create_database(self, name):
        self.summary = self.client.post("databases", body={"name": name})
        self.db_id = self.summary["id"]

    def open_database(self, db_id):
        self.summary = self.client.get("databases", db_id)
        self.db_id = db_id

    def import_database(self, path):
        """Завантажує локальний файл *.tdb.json на сервер як нову базу."""
        db = self.storage.load(path)
        self.summary = self.client.post("databases", "import", body=db.to_dict())
        self.db_id = self.summary["id"]

    def export_database(self, path):
        """Зберігає копію серверної бази в локальний файл."""
        data = self.client.get("databases", self.require_id(), "export")
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise StorageError(f"Не вдалося зберегти базу у «{path}»: {exc}")
        return path

    def save_database(self, path=None):
        self.summary = self.client.post("databases", self.require_id(), "save")
        return self.location()

    def discard_changes(self):
        self.summary = self.client.post("databases", self.require_id(), "discard")

    def close_database(self):
        self.db_id = None
        self.summary = None

    def require_id(self):
        if self.db_id is None:
            raise SchemaError("Спочатку створіть або відкрийте базу даних")
        return self.db_id

    def refresh_summary(self):
        self.summary = self.client.get("databases", self.require_id())

    def has_db(self):
        return self.db_id is not None

    def db_name(self):
        self.require_id()
        return self.summary["name"]

    def location(self):
        return f"сервер {urlparse(self.client.base_url).netloc}"

    def is_modified(self):
        return self.summary is not None and self.summary["modified"]

    def table_names(self):
        if self.db_id is None:
            return []
        self.refresh_summary()
        return self.summary["tables"]

    def get_table(self, name):
        return self.to_table(self.client.get("databases", self.require_id(), "tables", name))

    # --- таблиці ---

    def create_table(self, name, specs):
        body = {"name": name, "columns": [{"name": f, "type": t} for f, t in specs]}
        data = self.client.post("databases", self.require_id(), "tables", body=body)
        self.refresh_summary()
        return self.to_table(data)

    def drop_table(self, name):
        self.client.delete("databases", self.require_id(), "tables", name)
        self.refresh_summary()

    # --- рядки ---

    def add_row(self, table, raw):
        row = self.client.post("databases", self.require_id(), "tables", table, "rows",
                               body={"values": list(raw)})
        self.refresh_summary()
        return row

    def update_row(self, table, index, raw):
        row = self.client.put("databases", self.require_id(), "tables", table, "rows", index,
                              body={"values": list(raw)})
        self.refresh_summary()
        return row

    def delete_row(self, table, index):
        self.client.delete("databases", self.require_id(), "tables", table, "rows", index)
        self.refresh_summary()

    # --- операції ---

    def intersect_tables(self, a, b, result, save=False):
        body = {"left": a, "right": b, "result": result, "save": save}
        data = self.client.post("databases", self.require_id(), "intersection", body=body)
        self.refresh_summary()
        return self.to_table(data["table"])

    def to_table(self, data):
        return Table.from_dict(data, self.registry)
