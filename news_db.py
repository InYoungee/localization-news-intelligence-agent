import sqlite3
from datetime import datetime, timezone

DB_PATH = "news_agent.db"

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_articles_table(conn):
    """Adds the used_research tracking column if missing."""
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
    if "used_research" not in existing_columns:
        conn.execute("ALTER TABLE articles ADD COLUMN used_research INTEGER DEFAULT 0")
        print("✅ Added column 'used_research' to articles")
    conn.commit()

def initialize_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            link TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            excerpt TEXT,
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            processed INTEGER DEFAULT 0,
            importance_score INTEGER,
            category TEXT,
            summary TEXT,
            digested INTEGER DEFAULT 0
        )
        """
    )
    migrate_articles_table(conn)
    conn.commit()
    conn.close()


def insert_article(link, source, title, excerpt, published_at):
    """Insert only if this link hasn't been seen before — dedup by link."""
    conn = get_db()
    conn.execute(
        """
        INSERT OR IGNORE INTO articles (link, source, title, excerpt, published_at, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (link, source, title, excerpt, published_at, utc_now()),
    )
    conn.commit()
    conn.close()


def get_unprocessed_articles(limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM articles WHERE processed = 0 ORDER BY fetched_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_article_score(link, importance_score, category, summary, used_research=False):
    conn = get_db()
    conn.execute(
        """
        UPDATE articles
        SET processed = 1, importance_score = ?, category = ?, summary = ?, used_research = ?
        WHERE link = ?
        """,
        (importance_score, category, summary, int(used_research), link),
    )
    conn.commit()
    conn.close()


def mark_processing_failed(link):
    """Marks an article processed (so it isn't retried forever) but with
    no score — lets you distinguish 'skipped due to error' from 'scored low'."""
    conn = get_db()
    conn.execute("UPDATE articles SET processed = 1 WHERE link = ?", (link,))
    conn.commit()
    conn.close()

def requeue_unscored_articles():
    """Resets any article marked processed but with no score back to
    unprocessed — for retrying after a fix to a bug that caused scoring
    to fail (e.g. truncated responses, transient API errors)."""
    conn = get_db()
    result = conn.execute(
        "UPDATE articles SET processed = 0 WHERE processed = 1 AND importance_score IS NULL"
    )
    conn.commit()
    requeued = result.rowcount
    conn.close()
    print(f"Requeued {requeued} unscored article(s) for retry.")
    return requeued


def get_articles_for_digest(min_score=3):
    """Returns scored, undigested articles at or above the threshold,
    highest score first, grouped naturally by category for formatting."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT * FROM articles
        WHERE processed = 1 AND digested = 0
          AND importance_score >= ?
          AND category != 'Not Relevant'
        ORDER BY importance_score DESC, category ASC
        """,
        (min_score,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_as_digested(links):
    """Marks a batch of articles as delivered, so they're never sent twice."""
    if not links:
        return
    conn = get_db()
    conn.executemany(
        "UPDATE articles SET digested = 1 WHERE link = ?",
        [(link,) for link in links],
    )
    conn.commit()
    conn.close()



