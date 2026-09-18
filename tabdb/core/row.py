"""Рядок таблиці."""


class Row:
    """Впорядкований набір значень, що відповідає полям таблиці."""

    def __init__(self, values):
        self.values = list(values)

    def get(self, index):
        return self.values[index]

    def set(self, index, value):
        self.values[index] = value

    def key(self, columns):
        """Канонічний ключ рядка — основа порівняння рядків у перетині."""
        return tuple(
            col.dtype.normalize(value)
            for col, value in zip(columns, self.values)
        )

    def copy(self):
        return Row(self.values)

    def __len__(self):
        return len(self.values)
