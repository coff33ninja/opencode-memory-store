import sys
sys.path.insert(0, "src")
from opencode_memory_store.store import MemoryStore, get_db_path
import sqlite3

db = get_db_path()
store = MemoryStore(db)
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

query = "flutter"
like = f"%{query}%"
sql = "SELECT * FROM entities WHERE 1=1 AND (name LIKE ? OR text LIKE ? OR category LIKE ? OR tags LIKE ?) ORDER BY importance DESC, updated_at DESC LIMIT 10"
rows = conn.execute(sql, [like, like, like, like]).fetchall()
print(f"Direct SQL: {len(rows)} rows")
for r in rows:
    print(f"  {r['type']}: {r['name']}")

print("\nAll entities:")
for r in conn.execute("SELECT type, name, text FROM entities").fetchall():
    print(f"  type={r['type']!r} name={r['name']!r} text={r['text']!r}")

print("\nCalling store.recall directly:")
results = store.recall(query=query)
print(f"Results: {len(results)}")
for r in results:
    print(f"  {r['type']}: {r['name']}")
