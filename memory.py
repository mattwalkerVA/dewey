"""Memory system using SQLite FTS5 for full-text search retrieval."""

import json
import sqlite3
import time
from typing import Optional

import config


class Memory:
    """Store and retrieve teacher context using SQLite with FTS5 full-text search."""

    def __init__(self, db_path: str = str(config.DB_PATH)):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT '',
                timestamp REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                content='memories',
                content_rowid='id'
            );

            -- Triggers to keep FTS index in sync
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content)
                    VALUES('delete', old.id, old.content);
            END;
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content)
                    VALUES('delete', old.id, old.content);
                INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
            END;
        """)
        self.conn.commit()

    def store(
        self,
        content: str,
        collection: str,
        category: str = "",
        metadata: Optional[dict] = None,
    ) -> int:
        """Store a memory."""
        existing = self.find_exact(content=content, collection=collection, category=category)
        if existing is not None:
            return existing

        timestamp = time.time()
        meta_json = json.dumps(metadata or {})

        cursor = self.conn.execute(
            "INSERT INTO memories (collection, content, category, timestamp, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (collection, content, category, timestamp, meta_json),
        )
        self.conn.commit()
        return cursor.lastrowid

    def find_exact(self, content: str, collection: str, category: str = "") -> Optional[int]:
        """Return an existing memory id for an exact match, if present."""
        row = self.conn.execute(
            "SELECT id FROM memories WHERE collection = ? AND content = ? AND category = ?",
            (collection, content, category),
        ).fetchone()
        return row[0] if row else None

    def retrieve(
        self,
        query: str,
        collection: str,
        limit: int = config.MAX_MEMORY_RESULTS,
    ) -> list[dict]:
        """Retrieve memories by FTS5 relevance to query, falling back to recency."""
        # Try full-text search first
        rows = self._fts_search(query, collection, limit)

        # Fall back to most recent if FTS returns nothing
        if not rows:
            rows = self.conn.execute(
                "SELECT id, content, category, timestamp, metadata "
                "FROM memories WHERE collection = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (collection, limit),
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]

        return rows

    def _fts_search(self, query: str, collection: str, limit: int) -> list[dict]:
        """Run an FTS5 search, returning ranked results."""
        # Build an FTS query from the input — quote each token for prefix matching
        tokens = query.split()
        if not tokens:
            return []
        fts_query = " OR ".join(f'"{t}"*' for t in tokens)

        try:
            rows = self.conn.execute(
                """
                SELECT m.id, m.content, m.category, m.timestamp, m.metadata,
                       rank
                FROM memories_fts f
                JOIN memories m ON m.id = f.rowid
                WHERE memories_fts MATCH ?
                  AND m.collection = ?
                ORDER BY f.rank
                LIMIT ?
                """,
                (fts_query, collection, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # Malformed FTS query — fall back
            return []

        return [
            {
                "id": row[0],
                "content": row[1],
                "category": row[2],
                "timestamp": row[3],
                "metadata": json.loads(row[4]),
                "rank": row[5],
            }
            for row in rows
        ]

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "id": row[0],
            "content": row[1],
            "category": row[2],
            "timestamp": row[3],
            "metadata": json.loads(row[4]),
        }

    def get_all(self, collection: str) -> list[dict]:
        """Get all memories in a collection (used for teacher profile)."""
        rows = self.conn.execute(
            "SELECT id, content, category, timestamp, metadata "
            "FROM memories WHERE collection = ? ORDER BY timestamp",
            (collection,),
        ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def delete_collection(self, collection: str) -> int:
        """Delete all memories in a collection and return the number removed."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM memories WHERE collection = ?",
            (collection,),
        ).fetchone()
        count = row[0]
        self.conn.execute("DELETE FROM memories WHERE collection = ?", (collection,))
        self.conn.commit()
        return count

    def delete_all(self) -> int:
        """Delete all stored memories and return the number removed."""
        row = self.conn.execute("SELECT COUNT(*) FROM memories").fetchone()
        count = row[0]
        self.conn.execute("DELETE FROM memories")
        self.conn.commit()
        return count

    def has_profile(self) -> bool:
        """Check if a teacher profile exists."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM memories WHERE collection = ?",
            (config.PROFILE_COLLECTION,),
        ).fetchone()
        return row[0] > 0

    def store_exchange(self, teacher_msg: str, assistant_msg: str):
        """Store a conversation exchange."""
        combined = f"Teacher: {teacher_msg}\n\nAssistant: {assistant_msg}"
        self.store(
            content=combined,
            collection=config.CONVERSATION_COLLECTION,
            metadata={"teacher_msg": teacher_msg, "assistant_msg": assistant_msg},
        )

    def close(self):
        """Close the database connection."""
        self.conn.close()
