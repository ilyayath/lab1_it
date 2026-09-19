"""Індивідуальна операція варіанту: перетин таблиць."""

from ..core import Table
from ..datatypes import IncompatibleSchemaError
from .base import TableOperation


class IntersectionOperation(TableOperation):
    """Перетин двох таблиць з однаковими схемами.

    Результат містить ті рядки першої таблиці, які присутні й у другій.
    Дублікати не повторюються, порядок рядків успадковується від першої
    таблиці. Рядки порівнюються за ключами (Row.key), тому дійсні та
    комплексні дійсні значення зіставляються з допуском.

    Складність O(|A| + |B|) завдяки множині ключів другої таблиці.
    """

    name = "Перетин таблиць"

    def execute(self, tables, result_name):
        a, b = tables
        self._check_compatible(a, b)

        columns = a.columns
        result = Table(result_name, columns)

        keys_b = {row.key(columns) for row in b.get_rows()}
        seen = set()
        for row in a.get_rows():
            key = row.key(columns)
            if key in keys_b and key not in seen:
                result.append_row(row.copy())
                seen.add(key)
        return result

    @staticmethod
    def _check_compatible(a, b):
        if a.is_compatible(b):
            return
        raise IncompatibleSchemaError(
            "Схеми таблиць несумісні.\n"
            f"«{a.name}»: {describe(a)}\n"
            f"«{b.name}»: {describe(b)}"
        )


def describe(table):
    """Схема таблиці одним рядком — для повідомлень про помилку."""
    return ", ".join(f"{field}: {type_name}" for field, type_name in table.schema())
