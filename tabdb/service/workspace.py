"""Серверний рівень: набір баз даних у каталозі сервера."""

import re
import uuid
from pathlib import Path

from ..core import Database
from ..datatypes import NotFoundError, SchemaError, StorageError, TypeRegistry, ValidationError
from ..storage import JsonStorage
from .database_service import DatabaseService

# Ідентифікатор бази — ім'я її файлу без розширення; без крапок і слешів,
# щоб його не можна було використати для виходу за межі каталогу.
DB_ID = re.compile(r"^[\w-]{1,64}$")


class DatabaseWorkspace:
    """Каталог баз даних сервера.

    Кожна база зберігається у файлі <id>.tdb.json. Відкриті бази тримаються
    в пам'яті як сесії DatabaseService, тож зміни накопичуються до явного
    save() і можуть бути скасовані discard() — так само, як у десктоп-режимі.
    Цей клас не залежить від HTTP: його використовують і REST API, і тести,
    і майбутня веб-версія.
    """

    def __init__(self, root, storage=None, registry=None):
        self.registry = registry or TypeRegistry.default()
        self.storage = storage or JsonStorage(self.registry)
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.sessions = {}

    # --- каталог баз ---

    def list_ids(self):
        suffix = self.storage.extension
        return sorted(p.name[:-len(suffix)] for p in self.root.glob("*" + suffix))

    def list_databases(self):
        """Пари (id, сесія) для всіх баз каталогу; пошкоджені файли пропускаються."""
        result = []
        for db_id in self.list_ids():
            try:
                result.append((db_id, self.session(db_id)))
            except StorageError:
                continue
        return result

    def create_database(self, name):
        """Створює порожню базу й одразу записує її файл."""
        return self.add_database(Database(name))

    def import_database(self, data):
        """Додає базу з JSON-опису у форматі *.tdb.json."""
        try:
            db = Database.from_dict(data, self.registry)
        except (ValidationError, KeyError, TypeError, ValueError) as exc:
            raise StorageError(f"Опис бази має невідповідний формат: {exc}")
        return self.add_database(db)

    def add_database(self, db):
        db_id = uuid.uuid4().hex[:12]
        service = DatabaseService(self.storage, self.registry)
        service.db = db
        service.save_database(self.path_of(db_id))
        self.sessions[db_id] = service
        return db_id, service

    def delete_database(self, db_id):
        path = self.existing_path(db_id)
        self.sessions.pop(db_id, None)
        path.unlink()

    # --- окрема база ---

    def session(self, db_id):
        """Сесія бази: завантажує файл під час першого звернення."""
        if db_id not in self.sessions:
            service = DatabaseService(self.storage, self.registry)
            service.open_database(self.existing_path(db_id))
            self.sessions[db_id] = service
        return self.sessions[db_id]

    def save(self, db_id):
        self.session(db_id).save_database()

    def discard(self, db_id):
        """Скасовує незбережені зміни: наступне звернення перечитає файл."""
        self.existing_path(db_id)
        self.sessions.pop(db_id, None)

    # --- допоміжні ---

    def path_of(self, db_id):
        if not DB_ID.match(db_id):
            raise SchemaError(f"Некоректний ідентифікатор бази «{db_id}»")
        return self.root / (db_id + self.storage.extension)

    def existing_path(self, db_id):
        path = self.path_of(db_id)
        if not path.exists():
            raise NotFoundError(f"Бази «{db_id}» немає на сервері")
        return path
