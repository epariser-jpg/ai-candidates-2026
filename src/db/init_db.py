import sqlite3
from pathlib import Path
from src.config import DATABASE_PATH


SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    path = db_path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Initialize the database with the schema and seed data."""
    conn = get_connection(db_path)
    schema_sql = SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    conn.commit()
    return conn


def init_vec_table(conn: sqlite3.Connection):
    """Initialize the sqlite-vec virtual table for embeddings."""
    try:
        import sqlite_vec
        sqlite_vec.load(conn)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS excerpt_embeddings USING vec0(
                excerpt_id INTEGER PRIMARY KEY,
                embedding float[384]
            )
        """)
        conn.commit()
    except ImportError:
        print("Warning: sqlite-vec not installed. Semantic search will be unavailable.")
    except Exception as e:
        print(f"Warning: Could not initialize vector table: {e}")
