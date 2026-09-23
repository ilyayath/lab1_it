"""Тести клієнт-серверного режиму: REST API і RemoteDatabaseService."""

import tempfile
import unittest
from pathlib import Path

from tabdb.client import ApiClient, RemoteDatabaseService
from tabdb.datatypes import IncompatibleSchemaError, NotFoundError, ValidationError
from tabdb.service import DatabaseWorkspace

try:
    from fastapi.testclient import TestClient

    from tabdb.api import create_app
except ImportError:  # сервер не встановлено: pip install -r requirements.txt
    TestClient = None

SPECS = [("id", "integer"), ("z", "complexInteger"), ("w", "complexReal")]


@unittest.skipIf(TestClient is None, "потрібні fastapi та httpx")
class TestRemoteService(unittest.TestCase):
    """Тест 5. Десктоп-клієнт працює з базою на сервері через REST API."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.remote = self.connect()

    def connect(self):
        """Новий сервер над тим самим каталогом і клієнт до нього."""
        http = TestClient(create_app(DatabaseWorkspace(self.folder.name)))

        def transport(method, url, body):
            response = http.request(method, url, json=body)
            return response.status_code, response.content

        return RemoteDatabaseService(ApiClient("http://testserver", transport))

    def fill(self, service):
        service.create_database("Сенсори")
        for name, rows in (("A", [["1", "3+4i", "0.5i"], ["2", "-i", "1.5"]]),
                           ("B", [["2", "0-1i", "1.5+0i"], ["3", "7", "0"]])):
            service.create_table(name, SPECS)
            for raw in rows:
                service.add_row(name, raw)

    def test_rows_and_intersection(self):
        self.fill(self.remote)
        self.assertTrue(self.remote.is_modified())

        result = self.remote.intersect_tables("A", "B", "A_x_B", save=True)

        self.assertEqual([result.formatted_row(i) for i in range(result.row_count())],
                         [["2", "0-1i", "1.5+0i"]])
        self.assertIn("A_x_B", self.remote.table_names())

    def test_errors_come_back_as_exceptions(self):
        self.fill(self.remote)
        with self.assertRaises(ValidationError) as ctx:
            self.remote.add_row("A", ["x", "1.5+2i", "0"])
        self.assertEqual(set(ctx.exception.errors), {0, 1})

        with self.assertRaises(NotFoundError):
            self.remote.get_table("Немає")
        with self.assertRaises(NotFoundError):
            self.remote.delete_row("A", 99)

        self.remote.create_table("C", [("id", "integer")])
        with self.assertRaises(IncompatibleSchemaError):
            self.remote.intersect_tables("A", "C", "R")

    def test_save_and_discard(self):
        self.fill(self.remote)
        self.remote.save_database()
        self.assertFalse(self.remote.is_modified())

        self.remote.drop_table("B")
        self.remote.discard_changes()
        self.assertEqual(self.remote.table_names(), ["A", "B"])

        # Інший сервер над тим самим каталогом бачить збережену базу.
        other = self.connect()
        [summary] = other.list_databases()
        other.open_database(summary["id"])
        self.assertEqual(other.db_name(), "Сенсори")
        self.assertEqual(other.get_table("A").formatted_row(1), ["2", "0-1i", "1.5+0i"])


@unittest.skipIf(TestClient is None, "потрібні fastapi та httpx")
class TestWebClient(unittest.TestCase):
    """Тест 6. Сервер віддає веб-інтерфейс поруч з API."""

    def test_static_pages_and_api(self):
        web = Path(__file__).resolve().parent.parent / "web"
        with tempfile.TemporaryDirectory() as folder:
            http = TestClient(create_app(DatabaseWorkspace(folder), static_dir=web))
            page = http.get("/")
            types = http.get("/api/v1/types")

        self.assertEqual(page.status_code, 200)
        self.assertIn('<script src="app.js">', page.text)
        self.assertEqual(types.status_code, 200)
        self.assertIn("complexReal", [t["name"] for t in types.json()])


if __name__ == "__main__":
    unittest.main()
