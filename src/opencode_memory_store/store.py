import os, sqlite3, json, uuid, re, logging
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DIR = Path(os.environ.get("MEMORY_STORE_DIR") or Path.home() / ".memory-store")
LOG_FILE = str(DEFAULT_DIR / "store.log")

_logger = None

def _get_logger():
    global _logger
    if _logger:
        return _logger
    _logger = logging.getLogger("memory_store")
    _logger.setLevel(logging.DEBUG)
    if not _logger.handlers:
        try:
            Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            _logger.addHandler(fh)
        except Exception:
            pass
        sh = logging.StreamHandler()
        sh.setLevel(logging.WARNING)
        sh.setFormatter(logging.Formatter("[memory_store] %(levelname)s: %(message)s"))
        _logger.addHandler(sh)
    return _logger


def get_db_path(db_dir: str | None = None) -> str:
    p = Path(db_dir) if db_dir else DEFAULT_DIR
    p.mkdir(parents=True, exist_ok=True)
    return str(p / "store.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL DEFAULT 'memory',
    name TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    scope TEXT NOT NULL DEFAULT 'global',
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
CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
    name, text, category, tags,
    content='entities',
    content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
    INSERT INTO entities_fts(rowid, name, text, category, tags)
    VALUES (new.rowid, new.name, new.text, new.category, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, name, text, category, tags)
    VALUES ('delete', old.rowid, old.name, old.text, old.category, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, name, text, category, tags)
    VALUES ('delete', old.rowid, old.name, old.text, old.category, old.tags);
    INSERT INTO entities_fts(rowid, name, text, category, tags)
    VALUES (new.rowid, new.name, new.text, new.category, new.tags);
END;
"""


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for col in ("tags", "data"):
        try:
            d[col] = json.loads(d[col]) if isinstance(d[col], str) else d[col]
        except (json.JSONDecodeError, TypeError):
            d[col] = {} if col == "data" else []
    return d


def _fts_query(text: str) -> str:
    tokens = re.findall(r"[-\w]+", text)
    if not tokens:
        return ""
    return " AND ".join(tokens)


class MemoryStore:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._log = _get_logger()
        self._log.info("MemoryStore initialized at %s", db_path)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self._db_path)
        conn.executescript(SCHEMA)
        try:
            has_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            has_fts = conn.execute("SELECT COUNT(*) FROM entities_fts").fetchone()[0]
            if has_entities and has_fts == 0:
                self._log.info("Rebuilding FTS index for %d existing entities", has_entities)
                conn.executescript("INSERT INTO entities_fts(entities_fts) VALUES('rebuild')")
        except sqlite3.OperationalError as e:
            self._log.debug("FTS rebuild skipped (first init?): %s", e)
        conn.commit()
        conn.close()

    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def store(self, *, type: str = "memory", name: str = "", text: str = "",
              category: str = "general", scope: str = "global",
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
            self._log.info("Stored %s: %s (scope=%s, imp=%.1f)", type, eid[:8], scope, importance)
            return eid
        except Exception as e:
            self._log.error("store failed: %s", e, exc_info=True)
            raise
        finally:
            conn.close()

    def get(self, entity_id: str) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
            if row:
                self._log.debug("get %s: found", entity_id[:8])
                return _row_to_dict(row)
            self._log.debug("get %s: not found", entity_id[:8])
            return None
        except Exception as e:
            self._log.error("get failed: %s", e, exc_info=True)
            raise
        finally:
            conn.close()

    def recall(self, query: str = "", *, type: str | None = None,
               scope: str | None = None, category: str | None = None,
               limit: int = 10, min_importance: float = 0.0) -> list[dict]:
        conn = self._connect()
        log_extra = f"q={query!r}" if query else "no-query"
        if scope:
            log_extra += f" scope={scope}"
        if type:
            log_extra += f" type={type}"
        try:
            use_fts = bool(query) and _fts_query(query)
            if use_fts:
                sql = [
                    "SELECT e.* FROM entities e "
                    "JOIN entities_fts fts ON e.rowid = fts.rowid "
                    "WHERE entities_fts MATCH ?"
                ]
                params = [_fts_query(query)]
            else:
                sql = ["SELECT * FROM entities WHERE 1=1"]
                params = []
                if query:
                    like = f"%{query}%"
                    sql.append("AND (name LIKE ? OR text LIKE ? OR category LIKE ? OR tags LIKE ?)")
                    params.extend([like, like, like, like])
            if type:
                sql.append("AND e.type = ?" if use_fts else "AND type = ?")
                params.append(type)
            if scope:
                sql.append("AND e.scope = ?" if use_fts else "AND scope = ?")
                params.append(scope)
            if category:
                sql.append("AND e.category = ?" if use_fts else "AND category = ?")
                params.append(category)
            if min_importance > 0:
                sql.append("AND e.importance >= ?" if use_fts else "AND importance >= ?")
                params.append(min_importance)
            sql.append("ORDER BY e.importance DESC, e.updated_at DESC" if use_fts
                       else "ORDER BY importance DESC, updated_at DESC")
            sql.append("LIMIT ?")
            params.append(limit)
            try:
                rows = conn.execute(" ".join(sql), params).fetchall()
            except sqlite3.OperationalError as e:
                self._log.warning("FTS query failed, falling back to LIKE: %s", e)
                rows = []
            if use_fts and not rows:
                like = f"%{query}%"
                sql2 = ["SELECT * FROM entities WHERE (name LIKE ? OR text LIKE ? OR category LIKE ? OR tags LIKE ?)"]
                p2 = [like, like, like, like]
                if type:
                    sql2.append("AND type = ?"); p2.append(type)
                if scope:
                    sql2.append("AND scope = ?"); p2.append(scope)
                if category:
                    sql2.append("AND category = ?"); p2.append(category)
                if min_importance > 0:
                    sql2.append("AND importance >= ?"); p2.append(min_importance)
                sql2.append("ORDER BY importance DESC, updated_at DESC LIMIT ?")
                p2.append(limit)
                rows = conn.execute(" ".join(sql2), p2).fetchall()
            result = [_row_to_dict(r) for r in rows]
            self._log.info("recall (%s): %d results", log_extra, len(result))
            return result
        except Exception as e:
            self._log.error("recall failed (%s): %s", log_extra, e, exc_info=True)
            return []
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
            rows = conn.execute(" ".join(sql), params).fetchall()
            self._log.debug("list_entities (%s): %d rows", type or "all", len(rows))
            return [_row_to_dict(r) for r in rows]
        except Exception as e:
            self._log.error("list_entities failed: %s", e, exc_info=True)
            raise
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
                self._log.warning("update %s: no fields to update", entity_id[:8])
                return False
            sets.append("updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(entity_id)
            cur = conn.execute(f"UPDATE entities SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
            changed = cur.rowcount > 0
            self._log.info("update %s: %s (%d fields)", entity_id[:8], "changed" if changed else "not found", len(sets) - 1)
            return changed
        except Exception as e:
            self._log.error("update %s failed: %s", entity_id[:8], e, exc_info=True)
            raise
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
            n = cur.rowcount
            log_extra = entity_id[:8] if entity_id else query or scope or type or "all"
            if n:
                self._log.info("forget %s: deleted %d", log_extra, n)
            else:
                self._log.debug("forget %s: nothing matched", log_extra)
            return n
        except Exception as e:
            self._log.error("forget failed: %s", e, exc_info=True)
            raise
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
            self._log.info("stats: %d entities across %d types", total, len(by_type))
            return {
                "total": total,
                "by_type": by_type,
                "by_category": by_category,
                "by_scope": by_scope,
                "oldest_timestamp": row["oldest"] if row else None,
                "newest_timestamp": row["newest"] if row else None,
            }
        except Exception as e:
            self._log.error("stats failed: %s", e, exc_info=True)
            raise
        finally:
            conn.close()
