"""Винятки застосунку TabDB."""


class TabDBError(Exception):
    """Базовий виняток застосунку."""


class ValidationError(TabDBError):
    """Помилка валідації значення або рядка таблиці.

    errors відображає індекс поля на текст помилки. Для помилки окремого
    значення словник порожній, а текст доступний через str(exc).
    """

    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = dict(errors or {})


class SchemaError(TabDBError):
    """Некоректна схема таблиці або звернення до неіснуючої таблиці."""


class NotFoundError(SchemaError):
    """Звернення до неіснуючої бази, таблиці або рядка."""


class IncompatibleSchemaError(TabDBError):
    """Схеми таблиць несумісні для операції над таблицями."""


class StorageError(TabDBError):
    """Помилка читання або запису файлу бази даних."""
