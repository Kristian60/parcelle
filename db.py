import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "cellar.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS producers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                region      TEXT,
                country     TEXT,
                notes       TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS producer_styles (
                producer_id INTEGER REFERENCES producers(id),
                style       TEXT NOT NULL,
                PRIMARY KEY (producer_id, style)
            );

            CREATE TABLE IF NOT EXISTS sources (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                restaurant  TEXT NOT NULL,
                pdf_file    TEXT,
                imported_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS producer_sources (
                producer_id INTEGER REFERENCES producers(id),
                source_id   INTEGER REFERENCES sources(id),
                PRIMARY KEY (producer_id, source_id)
            );
        """)
    print("[OK] Database initialised")


def upsert_producer(name, region=None, country=None, notes=None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO producers (name, region, country, notes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                region  = COALESCE(excluded.region, region),
                country = COALESCE(excluded.country, country),
                notes   = COALESCE(excluded.notes, notes)
        """, (name, region, country, notes))
        row = conn.execute("SELECT id FROM producers WHERE name = ?", (name,)).fetchone()
        return row["id"]


def add_source(restaurant, pdf_file=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sources (restaurant, pdf_file) VALUES (?, ?)",
            (restaurant, pdf_file)
        )
        return cur.lastrowid


def link_producer_source(producer_id, source_id):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO producer_sources VALUES (?, ?)",
            (producer_id, source_id)
        )


def add_style(producer_id, style):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO producer_styles VALUES (?, ?)",
            (producer_id, style)
        )


def list_producers():
    with get_conn() as conn:
        return conn.execute("""
            SELECT p.id, p.name, p.region, p.country,
                   GROUP_CONCAT(DISTINCT ps.style) AS styles,
                   GROUP_CONCAT(DISTINCT s.restaurant) AS restaurants
            FROM producers p
            LEFT JOIN producer_styles ps ON ps.producer_id = p.id
            LEFT JOIN producer_sources psr ON psr.producer_id = p.id
            LEFT JOIN sources s ON s.id = psr.source_id
            GROUP BY p.id
            ORDER BY p.name
        """).fetchall()
