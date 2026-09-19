"""Інтерфейс операції над таблицями."""

from abc import ABC, abstractmethod


class TableOperation(ABC):
    """Операція, що з кількох таблиць будує нову таблицю."""

    name = ""

    @abstractmethod
    def execute(self, tables, result_name):
        """Виконує операцію й повертає нову таблицю з назвою result_name."""
