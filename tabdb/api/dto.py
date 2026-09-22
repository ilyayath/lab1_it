"""Перетворення доменних об'єктів на JSON-відповіді API.

Формат спільний для десктоп-клієнта і майбутньої веб-версії:
  - rows    — значення у форматі файлу *.tdb.json (точні, для програм);
  - display — ті самі значення текстом, як їх показувати й редагувати.
"""


def type_dto(dtype):
    return {"name": dtype.name, "hint": dtype.hint}


def database_dto(db_id, service):
    return {
        "id": db_id,
        "name": service.db_name(),
        "modified": service.is_modified(),
        "tables": service.table_names(),
    }


def table_dto(table):
    data = table.to_dict()
    data["display"] = [table.formatted_row(i) for i in range(table.row_count())]
    return data


def row_dto(table, index):
    return {"index": index, "display": table.formatted_row(index)}


def error_dto(exc):
    body = {"error": type(exc).__name__, "message": str(exc)}
    errors = getattr(exc, "errors", None)
    if errors:
        body["errors"] = {str(index): msg for index, msg in errors.items()}
    return body
