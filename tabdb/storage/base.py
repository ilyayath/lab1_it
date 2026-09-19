"""Інтерфейс сховища баз даних."""

from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Збереження бази даних на диск і зчитування її з диска."""

    extension = ""
    file_types = ()

    @abstractmethod
    def save(self, db, path):
        """Записує базу даних у файл."""

    @abstractmethod
    def load(self, path):
        """Зчитує базу даних із файлу."""
