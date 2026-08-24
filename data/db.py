import sqlite3
from contextlib import contextmanager

DB_PATH = "C:\\Users\\User\\source\\ffl-mgr\\fantasy.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
    finally:
        conn.close()