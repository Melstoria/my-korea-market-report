"""
Korea Market DB v2
"""
import sqlite3, os

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "../data/korea_market.db")
)

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS trading_volume (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        date       TEXT NOT NULL,
        rank       INTEGER NOT NULL,
        ticker     TEXT NOT NULL,
        name       TEXT NOT NULL,
        market     TEXT,
        sector     TEXT,
        close      REAL,
        change_pct REAL,
        volume     INTEGER,
        amount     REAL,
        market_cap REAL,
        prev_rank  INTEGER DEFAULT 0,
        UNIQUE(date, ticker)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS high_price (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        date       TEXT NOT NULL,
        ticker     TEXT NOT NULL,
        name       TEXT NOT NULL,
        market     TEXT,
        sector     TEXT,
        close      REAL,
        change_pct REAL,
        high_52w   REAL,
        vol_ratio  REAL DEFAULT 1,
        UNIQUE(date, ticker)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS upper_limit (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        date   TEXT NOT NULL,
        ticker TEXT NOT NULL,
        name   TEXT NOT NULL,
        market TEXT,
        sector TEXT,
        close  REAL,
        UNIQUE(date, ticker)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS sector_daily (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        date           TEXT NOT NULL,
        sector         TEXT NOT NULL,
        total_amount   REAL DEFAULT 0,
        stock_count    INTEGER DEFAULT 0,
        high_count     INTEGER DEFAULT 0,
        upper_count    INTEGER DEFAULT 0,
        avg_change_pct REAL DEFAULT 0,
        sector_score   REAL DEFAULT 0,
        UNIQUE(date, sector)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS sector_leadership (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        date           TEXT NOT NULL UNIQUE,
        top_sectors    TEXT,
        rotation_signal TEXT,
        market_summary TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS collection_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        date       TEXT NOT NULL,
        source     TEXT NOT NULL,
        status     TEXT NOT NULL,
        count      INTEGER DEFAULT 0,
        message    TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # 기존 DB에 컬럼 없으면 추가
    try:
        c.execute("ALTER TABLE trading_volume ADD COLUMN prev_rank INTEGER DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE high_price ADD COLUMN vol_ratio REAL DEFAULT 1")
    except: pass

    conn.commit()
    conn.close()
    print(f"[DB] Initialized: {DB_PATH}")

if __name__ == "__main__":
    init_db()
