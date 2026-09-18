"""Реєстр типів даних."""

from .errors import SchemaError
from .types import (
    CharType,
    ComplexIntegerType,
    ComplexRealType,
    IntegerType,
    RealType,
    StringType,
)


class TypeRegistry:
    """Відображення «назва типу → екземпляр DataType».

    Щоб додати новий тип, достатньо успадкувати DataType і зареєструвати
    його примірник.
    """

    def __init__(self):
        self._types = {}

    def register(self, dtype):
        self._types[dtype.name] = dtype

    def get(self, name):
        if name not in self._types:
            raise SchemaError(f"Невідомий тип «{name}»; доступні: {', '.join(self.names())}")
        return self._types[name]

    def names(self):
        return list(self._types)

    @staticmethod
    def default():
        """Реєстр із шістьма типами варіанту."""
        registry = TypeRegistry()
        for dtype in (IntegerType(), RealType(), CharType(), StringType(),
                      ComplexIntegerType(), ComplexRealType()):
            registry.register(dtype)
        return registry
