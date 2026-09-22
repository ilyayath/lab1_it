"""Сервер TabDB: REST API над каталогом баз даних.

Запуск: python server.py [--host 127.0.0.1] [--port 8000] [--data-dir data]
Веб-інтерфейс: http://127.0.0.1:8000/
Документація API: http://127.0.0.1:8000/docs
"""

import argparse
from pathlib import Path

import uvicorn

from tabdb.api import create_app
from tabdb.service import DatabaseWorkspace


def main():
    parser = argparse.ArgumentParser(description="Сервер TabDB")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default="data", help="каталог файлів баз даних")
    parser.add_argument("--web-dir", default=Path(__file__).parent / "web",
                        help="каталог веб-версії, що віддається з кореня (якщо існує)")
    args = parser.parse_args()

    app = create_app(DatabaseWorkspace(args.data_dir), static_dir=args.web_dir)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
