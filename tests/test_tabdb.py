"""Unit-тести до системи TabDB."""

import json
import tempfile
import unittest
from pathlib import Path

from tabdb.core import Column, Table
from tabdb.datatypes import (
    ComplexInteger,
    ComplexIntegerType,
    ComplexReal,
    ComplexRealType,
    IncompatibleSchemaError,
    IntegerType,
    RealType,
    StorageError,
    TypeRegistry,
    ValidationError,
)
from tabdb.operations import IntersectionOperation
from tabdb.service import DatabaseService

REGISTRY = TypeRegistry.default()

SPECS = [("id", "integer"), ("z", "complexInteger"), ("name", "string")]


def make_table(name, rows):
    """Допоміжна функція: таблиця зі схемою SPECS і заповненими рядками."""
    columns = [Column(field, REGISTRY.get(type_name)) for field, type_name in SPECS]
    table = Table(name, columns)
    for raw in rows:
        table.add_row(raw)
    return table


class TestDataTypes(unittest.TestCase):
    """Тест 1. Розбір значень, зокрема додаткових типів варіанту."""

    def test_integer(self):
        self.assertEqual(IntegerType().parse("-42"), -42)
        with self.assertRaises(ValidationError):
            IntegerType().parse("3.5")

    def test_complex_integer(self):
        dtype = ComplexIntegerType()
        self.assertEqual(dtype.parse("3+4i"), ComplexInteger(3, 4))
        self.assertEqual(dtype.parse("3 - 4i"), ComplexInteger(3, -4))
        self.assertEqual(dtype.parse("5i"), ComplexInteger(0, 5))
        self.assertEqual(dtype.parse("7"), ComplexInteger(7, 0))
        with self.assertRaises(ValidationError):
            dtype.parse("3.5+4i")

    def test_complex_real(self):
        dtype = ComplexRealType()
        self.assertEqual(dtype.parse("3.5-0.25i"), ComplexReal(3.5, -0.25))
        self.assertTrue(ComplexReal(1.0, 2.0).is_close(ComplexReal(1.0, 2.0)))
        with self.assertRaises(ValidationError):
            dtype.parse("hello")
        with self.assertRaises(ValidationError):
            dtype.parse("1e400+2i")


    def test_real_formatting_round_trips(self):
        # Показаний у GUI текст має розбиратися назад без втрати точності.
        real, complex_real = RealType(), ComplexRealType()
        for value in (3.14159265358979, 1e-05, -2.5e16, 1.0, 0.1 + 0.2):
            self.assertEqual(real.parse(real.format(value)), value)
            z = ComplexReal(value, -value)
            self.assertEqual(complex_real.parse(complex_real.format(z)), z)
        self.assertEqual(real.format(1.0), "1")
        # Великі числа порівнюються в перетині без переповнення.
        self.assertEqual(real.normalize(1e300), 1e300)
        self.assertEqual(complex_real.format(ComplexReal(1.5, 0.0)), "1.5+0i")


class TestTable(unittest.TestCase):
    """Тест 2. Валідація та редагування рядків таблиці."""

    def test_add_row(self):
        table = make_table("T", [["1", "3+4i", "перший"]])
        self.assertEqual(table.row_count(), 1)
        self.assertEqual(table.formatted_row(0), ["1", "3+4i", "перший"])

    def test_invalid_row_is_rejected(self):
        table = make_table("T", [])
        with self.assertRaises(ValidationError) as ctx:
            table.add_row(["x", "3.5+4i", "текст"])
        # Помилки зібрано з обох хибних полів, рядок у таблицю не потрапив.
        self.assertEqual(set(ctx.exception.errors), {0, 1})
        self.assertEqual(table.row_count(), 0)

    def test_update_and_delete_row(self):
        table = make_table("T", [["1", "1+1i", "a"], ["2", "2+2i", "b"]])
        table.update_row(0, ["10", "5-5i", "оновлено"])
        self.assertEqual(table.formatted_row(0), ["10", "5-5i", "оновлено"])
        table.delete_row(0)
        self.assertEqual(table.row_count(), 1)


class TestIntersection(unittest.TestCase):
    """Тест 3. Індивідуальна операція варіанту — перетин таблиць."""

    def test_intersection(self):
        a = make_table("A", [
            ["1", "3+4i", "альфа"],
            ["2", "0-1i", "бета"],
            ["3", "5+0i", "гамма"],
        ])
        b = make_table("B", [
            ["9", "9+9i", "омега"],
            ["2", "0-1i", "бета"],
            ["3", "5+0i", "гамма"],
        ])

        result = IntersectionOperation().execute([a, b], "A_x_B")

        self.assertEqual(result.schema(), a.schema())
        self.assertEqual(
            [result.formatted_row(i) for i in range(result.row_count())],
            [["2", "0-1i", "бета"], ["3", "5+0i", "гамма"]],
        )

    def test_intersection_needs_same_schema(self):
        a = make_table("A", [])
        other = Table("B", [Column("id", REGISTRY.get("integer"))])
        with self.assertRaises(IncompatibleSchemaError):
            IntersectionOperation().execute([a, other], "R")


class TestStorage(unittest.TestCase):
    """Тест 4. Збереження бази на диск і зчитування її з диска."""

    def test_save_and_load(self):
        service = DatabaseService()
        service.create_database("lab1")
        service.create_table("Mixed", [
            ("id", "integer"),
            ("ratio", "real"),
            ("mark", "char"),
            ("note", "string"),
            ("z", "complexInteger"),
            ("w", "complexReal"),
        ])
        service.add_row("Mixed", ["7", "-3.25", "A", "Київ", "3+4i", "1.5-0.25i"])

        with tempfile.TemporaryDirectory() as folder:
            path = service.save_database(Path(folder) / "lab1.tdb.json")
            self.assertFalse(service.is_modified())

            reader = DatabaseService()
            reader.open_database(path)

            # Файл зі значенням не того типу не відкривається.
            data = json.loads(path.read_text(encoding="utf-8"))
            data["tables"][0]["rows"][0][0] = "abc"
            broken = Path(folder) / "broken.tdb.json"
            broken.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(StorageError):
                DatabaseService().open_database(broken)

        table = reader.get_table("Mixed")
        self.assertEqual(table.schema(), service.get_table("Mixed").schema())
        self.assertEqual(
            table.get_rows()[0].values,
            [7, -3.25, "A", "Київ", ComplexInteger(3, 4), ComplexReal(1.5, -0.25)],
        )


if __name__ == "__main__":
    unittest.main()
