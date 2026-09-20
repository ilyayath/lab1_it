"""Фасад прикладного рівня: єдина точка входу GUI у систему."""

from pathlib import Path

from ..core import Column, Database
from ..datatypes import SchemaError, TypeRegistry
from ..operations import IntersectionOperation
from ..storage import JsonStorage


class DatabaseService:
    """Керує поточною базою даних, її збереженням та операціями над таблицями.

    GUI не звертається до доменних класів напряму — весь сценарій проходить
    через цей фасад, який також підтримує стан «база змінена».

    Той самий інтерфейс реалізує RemoteDatabaseService (tabdb.client), тож GUI
    однаково працює з локальним файлом і з базою на сервері. На сервері
    DatabaseWorkspace тримає по одному такому фасаду на кожну базу.
    """

    is_remote = False

    def __init__(self, storage=None, registry=None):
        self.registry = registry or TypeRegistry.default()
        self.storage = storage or JsonStorage(self.registry)
        self.intersection = IntersectionOperation()
        self.db = None
        self.path = None

    # --- база даних ---

    def create_database(self, name):
        """UC-01: створити нову порожню базу даних."""
        self.db = Database(name)
        self.db.mark_modified()
        self.path = None
        return self.db

    def open_database(self, path):
        """UC-02: відкрити базу даних із диска."""
        self.db = self.storage.load(path)
        self.path = Path(path)
        return self.db

    def save_database(self, path=None):
        """UC-03: зберегти поточну базу даних на диск."""
        db = self.require_db()
        path = Path(path) if path else self.path
        if path is None:
            raise SchemaError("Не вказано шлях до файлу бази даних")
        self.storage.save(db, path)
        self.path = path
        db.mark_saved()
        return path

    def close_database(self):
        self.db = None
        self.path = None

    def discard_changes(self):
        """Скасовує незбережені зміни: перечитує файл або закриває нову базу."""
        if self.path is None:
            self.close_database()
        else:
            self.open_database(self.path)

    def require_db(self):
        """Повертає поточну базу або кидає помилку, якщо її не відкрито."""
        if self.db is None:
            raise SchemaError("Спочатку створіть або відкрийте базу даних")
        return self.db

    def has_db(self):
        return self.db is not None

    def db_name(self):
        return self.require_db().name

    def location(self):
        """Де зберігається база — для заголовка вікна."""
        return self.path.name if self.path else "не збережено"

    def is_modified(self):
        return self.db is not None and self.db.is_modified()

    def table_names(self):
        return [] if self.db is None else self.db.table_names()

    def get_table(self, name):
        return self.require_db().get_table(name)

    # --- таблиці ---

    def create_table(self, name, specs):
        """UC-04: створити таблицю зі схеми «назва поля → назва типу»."""
        db = self.require_db()
        if not specs:
            raise SchemaError("Таблиця повинна мати хоча б одне поле")
        columns = [Column(field, self.registry.get(type_name)) for field, type_name in specs]
        return db.create_table(name, columns)

    def drop_table(self, name):
        """UC-05: видалити таблицю з бази."""
        self.require_db().drop_table(name)

    # --- рядки ---

    def add_row(self, table, raw):
        """UC-07: додати валідований рядок до таблиці."""
        db = self.require_db()
        row = db.get_table(table).add_row(raw)
        db.mark_modified()
        return row

    def update_row(self, table, index, raw):
        """UC-08: відредагувати рядок таблиці."""
        db = self.require_db()
        row = db.get_table(table).update_row(index, raw)
        db.mark_modified()
        return row

    def delete_row(self, table, index):
        """UC-09: видалити рядок таблиці."""
        db = self.require_db()
        db.get_table(table).delete_row(index)
        db.mark_modified()

    # --- операції ---

    def intersect_tables(self, a, b, result, save=False):
        """UC-10: перетин двох таблиць поточної бази.

        За save=True результат додається до бази як нова таблиця.
        """
        db = self.require_db()
        result = result.strip()
        if not result:
            raise SchemaError("Назва таблиці-результату не може бути порожньою")
        if save and db.has_table(result):
            raise SchemaError(f"Таблиця «{result}» уже існує; оберіть іншу назву")

        table = self.intersection.execute([db.get_table(a), db.get_table(b)], result)
        if save:
            db.add_table(table)
        return table
