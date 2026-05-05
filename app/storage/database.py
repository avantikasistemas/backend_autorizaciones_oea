from collections.abc import Iterator
from contextlib import contextmanager

import pyodbc

from app.config import get_settings


@contextmanager
def get_connection() -> Iterator[pyodbc.Connection]:
    connection = pyodbc.connect(get_settings().sql_connection_string)
    try:
        yield connection
    finally:
        connection.close()
