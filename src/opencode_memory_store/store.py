import sqlite3, json, uuid
from datetime import datetime, timezone
from pathlib import Path


def get_db_path(db_dir: str | None = None) -> str:
    p = Path(db_dir) if db_dir else Path.home() / ".opencode" / "memory"
    p.mkdir(parents=True, exist_ok=True)
    return str(p / "store.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('memory','project','person','skill','session','config')),
    name TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    scope TEXT NOT NULL DEFAULT 'admin:global',
    importance REAL NOT NULL DEFAULT 0.5,
    tags TEXT NOT NULL DEFAULT '[]',
    data TEXT NOT NULL DEFAULT '{}',
    source TEXT DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_scope ON entities(scope);
CREATE INDEX IF NOT EXISTS idx_entities_category ON entities(category);
CREATE INDEX IF NOT EXISTS idx_entities_importance ON entities(importance);
"""


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for col in ("tags", "data"):
        try:
            d[col] = json.loads(d[col]) if isinstance(d[col], str) else d[col]
        except (json.JSONDecodeError, TypeError):
            d[col] = {} if col == "data" else []
    return d


class MemoryStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self._db_path)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def store(self, *, type: str = "memory", name: str = "", text: str = "",
              category: str = "general", scope: str = "admin:global",
              importance: float = 0.5, tags: list | None = None,
              data: dict | None = None, source: str = "manual") -> str:
        eid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO entities (id,type,name,text,category,scope,importance,tags,data,source,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (eid, type, name, text, category, scope, importance,
                 json.dumps(tags or []), json.dumps(data or {}), source, now, now)
            )
            conn.commit()
            return eid
        finally:
            conn.close()

    def get(self, entity_id: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
            return _row_to_dict(row) if row else None
        finally:
            conn.close()

    def recall(self, query: str = "", *, type: str | None = None,
               scope: str | None = None, category: str | None = None,
               limit: int = 10, min_importance: float = 0.0) -> list[dict]:
        conn = self._connect()
        try:
            sql = ["SELECT * FROM entities WHERE 1=1"]
            params = []
            if type:
                sql.append("AND type = ?")
                params.append(type)
            if scope:
                sql.append("AND scope = ?")
                params.append(scope)
            if category:
                sql.append("AND category = ?")
                params.append(category)
            if min_importance > 0:
                sql.append("AND importance >= ?")
                params.append(min_importance)
            if query:
                like = f"%{query}%"
                sql.append("AND (name LIKE ? OR text LIKE ? OR category LIKE ? OR tags LIKE ?)")
                params.extend([like, like, like, like])
            sql.append("ORDER BY importance DESC, updated_at DESC")
            sql.append("LIMIT ?")
            params.append(limit)
            return [_row_to_dict(r) for r in conn.execute(" ".join(sql), params).fetchall()]
        finally:
            conn.close()

    def list_entities(self, *, type: str | None = None,
                      scope: str | None = None, category: str | None = None,
                      limit: int = 50) -> list[dict]:
        conn = self._connect()
        try:
            sql = ["SELECT * FROM entities WHERE 1=1"]
            params = []
            if type:
                sql.append("AND type = ?")
                params.append(type)
            if scope:
                sql.append("AND scope = ?")
                params.append(scope)
            if category:
                sql.append("AND category = ?")
                params.append(category)
            sql.append("ORDER BY updated_at DESC")
            sql.append("LIMIT ?")
            params.append(limit)
            return [_row_to_dict(r) for r in conn.execute(" ".join(sql), params).fetchall()]
        finally:
            conn.close()

    def update(self, entity_id: str, *, name: str | None = None,
               text: str | None = None, category: str | None = None,
               importance: float | None = None, scope: str | None = None,
               tags: list | None = None, data: dict | None = None) -> bool:
        conn = self._connect()
        try:
            sets = []
            params = []
            if name is not None:
                sets.append("name = ?"); params.append(name)
            if text is not None:
                sets.append("text = ?"); params.append(text)
            if category is not None:
                sets.append("category = ?"); params.append(category)
            if importance is not None:
                sets.append("importance = ?"); params.append(importance)
            if scope is not None:
                sets.append("scope = ?"); params.append(scope)
            if tags is not None:
                sets.append("tags = ?"); params.append(json.dumps(tags))
            if data is not None:
                sets.append("data = ?"); params.append(json.dumps(data))
            if not sets:
                return False
            sets.append("updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(entity_id)
            cur = conn.execute(f"UPDATE entities SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def forget(self, entity_id: str | None = None,
               query: str | None = None, scope: str | None = None,
               type: str | None = None) -> int:
        conn = self._connect()
        try:
            sql = ["DELETE FROM entities WHERE 1=1"]
            params = []
            if entity_id:
                sql.append("AND id = ?"); params.append(entity_id)
            if query:
                like = f"%{query}%"
                sql.append("AND (name LIKE ? OR text LIKE ?)"); params.extend([like, like])
            if scope:
                sql.append("AND scope = ?"); params.append(scope)
            if type:
                sql.append("AND type = ?"); params.append(type)
            cur = conn.execute(" ".join(sql), params)
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def stats(self) -> dict:
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            by_type = {}
            by_category = {}
            by_scope = {}
            for r in conn.execute("SELECT type, COUNT(*) as cnt FROM entities GROUP BY type").fetchall():
                by_type[r["type"]] = r["cnt"]
            for r in conn.execute("SELECT category, COUNT(*) as cnt FROM entities GROUP BY category").fetchall():
                by_category[r["category"]] = r["cnt"]
            for r in conn.execute("SELECT scope, COUNT(*) as cnt FROM entities GROUP BY scope").fetchall():
                by_scope[r["scope"]] = r["cnt"]
            row = conn.execute("SELECT MIN(created_at) as oldest, MAX(updated_at) as newest FROM entities").fetchone()
            return {
                "total": total,
                "by_type": by_type,
                "by_category": by_category,
                "by_scope": by_scope,
                "oldest_timestamp": row["oldest"] if row else None,
                "newest_timestamp": row["newest"] if row else None,
            }
        finally:
            conn.close()
