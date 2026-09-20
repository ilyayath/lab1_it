"""Точка входу застосунку TabDB.

Запуск:
  python main.py                                   локальна робота з файлами
  python main.py --server http://127.0.0.1:8000    клієнт сервера TabDB
"""

import argparse

from tabdb.gui import MainWindow


def main():
    parser = argparse.ArgumentParser(description="TabDB — десктоп-клієнт")
    parser.add_argument("--server", metavar="URL",
                        help="адреса сервера TabDB; без неї бази зберігаються локально")
    args = parser.parse_args()

    service = None
    if args.server:
        from tabdb.client import ApiClient, RemoteDatabaseService
        service = RemoteDatabaseService(ApiClient(args.server))
    MainWindow(service).mainloop()


if __name__ == "__main__":
    main()
