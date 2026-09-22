"""REST API сервера TabDB (FastAPI).

Усі маршрути мають префікс /api/v1. Той самий API використовують
десктоп-клієнт (tabdb.client) і майбутня веб-версія; інтерактивна
документація доступна за адресою /docs.

Обробники оголошено як async: вони виконуються по черзі в одному потоці
циклу подій, тому спільні сесії DatabaseWorkspace не потребують блокувань.
"""

from pathlib import Path

from fastapi import APIRouter, Body, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..datatypes import (
    IncompatibleSchemaError,
    NotFoundError,
    StorageError,
    TabDBError,
    ValidationError,
)
from ..service import DatabaseWorkspace
from .dto import database_dto, error_dto, row_dto, table_dto, type_dto

API_PREFIX = "/api/v1"

# Відповідність винятків застосунку кодам HTTP (решта TabDBError — 400).
STATUS_CODES = {
    NotFoundError: 404,
    ValidationError: 422,
    IncompatibleSchemaError: 409,
    StorageError: 400,
}


class DatabaseCreate(BaseModel):
    name: str


class ColumnSpec(BaseModel):
    name: str
    type: str


class TableCreate(BaseModel):
    name: str
    columns: list[ColumnSpec]


class RowValues(BaseModel):
    values: list[str]


class IntersectionRequest(BaseModel):
    left: str
    right: str
    result: str
    save: bool = True


def status_of(exc):
    for cls in type(exc).__mro__:
        if cls in STATUS_CODES:
            return STATUS_CODES[cls]
    return 400


def create_app(workspace, static_dir=None):
    """Створює застосунок FastAPI над заданим DatabaseWorkspace.

    static_dir — каталог зі статичною веб-версією; якщо його вказано,
    вона віддається з кореня сайту поруч з API.
    """
    app = FastAPI(title="TabDB API", version="1.0")
    app.state.workspace = workspace

    @app.exception_handler(TabDBError)
    async def on_tabdb_error(request: Request, exc: TabDBError):
        return JSONResponse(error_dto(exc), status_code=status_of(exc))

    @app.exception_handler(RequestValidationError)
    async def on_bad_request(request: Request, exc: RequestValidationError):
        details = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors())
        body = {"error": "BadRequest", "message": f"Некоректний запит: {details}"}
        return JSONResponse(body, status_code=400)

    app.include_router(build_router(workspace), prefix=API_PREFIX)

    if static_dir is not None and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    return app


def build_router(ws: DatabaseWorkspace):
    router = APIRouter()

    # --- довідники ---

    @router.get("/types")
    async def list_types():
        return [type_dto(ws.registry.get(name)) for name in ws.registry.names()]

    # --- бази даних ---

    @router.get("/databases")
    async def list_databases():
        return [database_dto(db_id, s) for db_id, s in ws.list_databases()]

    @router.post("/databases", status_code=201)
    async def create_database(body: DatabaseCreate):
        return database_dto(*ws.create_database(body.name))

    @router.post("/databases/import", status_code=201)
    async def import_database(data: dict = Body(...)):
        return database_dto(*ws.import_database(data))

    @router.get("/databases/{db_id}")
    async def get_database(db_id: str):
        return database_dto(db_id, ws.session(db_id))

    @router.delete("/databases/{db_id}", status_code=204)
    async def delete_database(db_id: str):
        ws.delete_database(db_id)
        return Response(status_code=204)

    @router.post("/databases/{db_id}/save")
    async def save_database(db_id: str):
        ws.save(db_id)
        return database_dto(db_id, ws.session(db_id))

    @router.post("/databases/{db_id}/discard")
    async def discard_changes(db_id: str):
        ws.discard(db_id)
        return database_dto(db_id, ws.session(db_id))

    @router.get("/databases/{db_id}/export")
    async def export_database(db_id: str):
        session = ws.session(db_id)
        filename = f"{db_id}{ws.storage.extension}"
        return JSONResponse(
            session.db.to_dict(),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # --- таблиці ---

    @router.post("/databases/{db_id}/tables", status_code=201)
    async def create_table(db_id: str, body: TableCreate):
        specs = [(col.name, col.type) for col in body.columns]
        return table_dto(ws.session(db_id).create_table(body.name, specs))

    @router.get("/databases/{db_id}/tables/{table}")
    async def get_table(db_id: str, table: str):
        return table_dto(ws.session(db_id).get_table(table))

    @router.delete("/databases/{db_id}/tables/{table}", status_code=204)
    async def drop_table(db_id: str, table: str):
        ws.session(db_id).drop_table(table)
        return Response(status_code=204)

    # --- рядки ---

    @router.post("/databases/{db_id}/tables/{table}/rows", status_code=201)
    async def add_row(db_id: str, table: str, body: RowValues):
        session = ws.session(db_id)
        session.add_row(table, body.values)
        target = session.get_table(table)
        return row_dto(target, target.row_count() - 1)

    @router.put("/databases/{db_id}/tables/{table}/rows/{index}")
    async def update_row(db_id: str, table: str, index: int, body: RowValues):
        session = ws.session(db_id)
        session.update_row(table, index, body.values)
        return row_dto(session.get_table(table), index)

    @router.delete("/databases/{db_id}/tables/{table}/rows/{index}", status_code=204)
    async def delete_row(db_id: str, table: str, index: int):
        ws.session(db_id).delete_row(table, index)
        return Response(status_code=204)

    # --- операції ---

    @router.post("/databases/{db_id}/intersection")
    async def intersect_tables(db_id: str, body: IntersectionRequest):
        result = ws.session(db_id).intersect_tables(
            body.left, body.right, body.result, body.save)
        return {"table": table_dto(result), "saved": body.save}

    return router
