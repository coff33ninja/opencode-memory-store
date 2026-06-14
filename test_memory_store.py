"""
Validate the memory store works correctly across scopes, types, and queries.
Uses an isolated temp DB so it won't touch real data.
"""

import os, sys, json, tempfile, shutil, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from opencode_memory_store.store import MemoryStore

PASS = 0
FAIL = 0
tmpdir = None

def ok(name):
    global PASS
    PASS += 1
    print(f"  PASS  {name}")

def fail(name, detail=""):
    global FAIL
    FAIL += 1
    msg = f"  FAIL  {name}"
    if detail:
        msg += f"\n        {detail}"
    print(msg)

def scope_test(store):
    print("\n=== Scope isolation ===")
    store.store(type="memory", name="foo-config", text="Foo app config", scope="project:foo", importance=0.9)
    store.store(type="memory", name="bar-config", text="Bar app config", scope="project:bar", importance=0.9)
    store.store(type="fact", name="global-truth", text="Pi is 3.14159", scope="global", importance=0.8)
    store.store(type="note", name="user-pref", text="User likes dark mode", scope="user:alice", importance=0.5)

    foo = store.recall(scope="project:foo")
    ok("project:foo returns only foo entries") if len(foo) == 1 and foo[0]["name"] == "foo-config" else fail("project:foo isolation", f"got {len(foo)} items")

    bar = store.recall(scope="project:bar")
    ok("project:bar returns only bar entries") if len(bar) == 1 and bar[0]["name"] == "bar-config" else fail("project:bar isolation", f"got {len(bar)} items")

    both = store.recall(scope="global")
    ok("global scope returns only global entries") if len(both) == 1 and both[0]["name"] == "global-truth" else fail("global scope isolation", f"got {[e['name'] for e in both]}")

    user = store.recall(scope="user:alice")
    ok("user:alice scope returns only alice entries") if len(user) == 1 and user[0]["name"] == "user-pref" else fail("user:alice isolation", f"got {len(user)} items")

def type_filter_test(store):
    print("\n=== Type filtering ===")
    all_notes = store.recall(type="note")
    ok("recall type=note returns only notes") if all(e["type"] == "note" for e in all_notes) else fail("type filter note")

    all_memory = store.recall(type="memory")
    ok("recall type=memory returns only memories") if all(e["type"] == "memory" for e in all_memory) else fail("type filter memory")

    list_memory = store.list_entities(type="memory")
    ok("list type=memory returns only memories") if len(list_memory) == 2 else fail("list type=memory count", f"got {len(list_memory)}")

def recall_test(store):
    print("\n=== FTS5 recall ===")
    r = store.recall("dark mode")
    ok("recall 'dark mode' finds user preference") if len(r) >= 1 else fail("recall dark mode", f"got {len(r)}")

    r = store.recall("Pi")
    ok("recall 'Pi' finds global truth") if len(r) >= 1 and r[0]["name"] == "global-truth" else fail("recall Pi", f"got {[e['name'] for e in r]}")

    r = store.recall("Foo")
    ok("recall 'Foo' finds foo config") if len(r) >= 1 and r[0]["name"] == "foo-config" else fail("recall Foo")

def recall_fallback_test(store):
    print("\n=== FTS5 fallback (non-alphanumeric query) ===")
    r = store.recall("3.14159")
    ok("recall numeric '3.14159' via LIKE fallback") if len(r) >= 1 else fail("recall numeric fallback")

    r = store.recall("???")
    ok("recall '???' returns nothing") if len(r) == 0 else fail("recall gibberish")

def importance_filter_test(store):
    print("\n=== Importance filtering ===")
    high = store.recall(min_importance=0.85)
    ok("min_importance=0.85 returns only high-imp entries") if len(high) == 2 else fail("high importance count", f"got {len(high)}")

    medium = store.recall(min_importance=0.6)
    ok("min_importance=0.6 returns mid+high entries") if len(medium) == 3 else fail("mid importance count", f"got {len(medium)}")

def update_test(store):
    print("\n=== Update ===")
    items = store.recall("foo-config")
    if not items:
        fail("update - find foo-config", "not found")
        return
    eid = items[0]["id"]
    updated_ok = store.update(eid, text="Foo app config — updated", importance=1.0, scope="project:foo")
    ok("update returns True") if updated_ok else fail("update return value")

    updated = store.get(eid)
    ok("updated text matches") if updated and updated["text"] == "Foo app config — updated" else fail("update text", f"got '{updated['text'] if updated else 'N/A'}'")
    ok("updated importance matches") if updated and updated["importance"] == 1.0 else fail("update importance", f"got {updated['importance'] if updated else 'N/A'}")
    ok("updated scope preserved") if updated and updated["scope"] == "project:foo" else fail("update scope")

def forget_test(store):
    print("\n=== Forget ===")
    items = store.recall(scope="user:alice")
    if not items:
        fail("forget - find user:alice", "not found")
        return
    eid = items[0]["id"]

    n = store.forget(entity_id=eid)
    ok("forget by ID returns 1") if n == 1 else fail("forget count", f"got {n}")

    gone = store.get(eid)
    ok("forget entity no longer exists") if gone is None else fail("forget still exists")

    n = store.forget(type="note")
    ok("forget by type returns 0 (already deleted)") if n == 0 else fail("forget type after id", f"got {n}")

def path_tracking_test(store):
    print("\n=== Path tracking ===")
    real_dir = Path(tempfile.mkdtemp(prefix="path_test_"))
    real_file = real_dir / "README.md"
    real_file.write_text("# Test Project")
    store.store(type="project", name="test-proj", text="A test project",
                scope="project:test-proj", importance=0.9,
                data={"path": str(real_file.parent)})
    store.store(type="project", name="ghost-proj", text="A ghost project",
                scope="project:ghost", importance=0.9,
                data={"path": str(real_dir / "nonexistent" / "subdir")})
    r = store.recall(scope="project:test-proj")
    ok("recall with path returns entity") if len(r) >= 1 else fail("path recall entity")
    data = r[0].get("data", {})
    if isinstance(data, str):
        try: data = json.loads(data)
        except: data = {}
    p = data.get("path", "") if isinstance(data, dict) else ""
    ok("data.path stored correctly") if "path_test_" in str(p) else fail("data.path", f"got {p}")
    shutil.rmtree(str(real_dir), ignore_errors=True)


def stats_test(store):
    print("\n=== Stats ===")
    s = store.stats()
    ok("stats total > 0") if s["total"] > 0 else fail("stats total", f"got {s['total']}")
    ok("stats by_type has entries") if len(s["by_type"]) > 0 else fail("stats by_type")
    ok("stats by_scope has entries") if len(s["by_scope"]) > 0 else fail("stats by_scope")
    ok("stats has timestamps") if s["oldest_timestamp"] and s["newest_timestamp"] else fail("stats timestamps")


if __name__ == "__main__":
    tmpdir = tempfile.mkdtemp(prefix="memory_store_test_")
    db_path = os.path.join(tmpdir, "test.db")
    print(f"Using temp DB: {db_path}")
    store = MemoryStore(db_path)

    scope_test(store)
    type_filter_test(store)
    recall_test(store)
    recall_fallback_test(store)
    importance_filter_test(store)
    update_test(store)
    forget_test(store)
    path_tracking_test(store)
    stats_test(store)

    shutil.rmtree(tmpdir, ignore_errors=True)

    total = PASS + FAIL
    print(f"\n{'='*40}")
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    if FAIL:
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)
