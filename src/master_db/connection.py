import sqlite3
from contextlib import contextmanager
from src.config import MASTER_DB_PATH

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def test_connection():
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1")
        return True
    except:
        return False
