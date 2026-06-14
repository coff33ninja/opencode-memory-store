import sys, json, argparse
from pathlib import Path
from .store import MemoryStore, get_db_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["store", "get", "recall", "list", "update", "forget", "stats", "ingest", "import", "verify-paths"])
    parser.add_argument("text", nargs="?", default="")
    parser.add_argument("--db-dir")
    parser.add_argument("--type", default=None)
    parser.add_argument("--name", default="")
    parser.add_argument("--category", default="general")
    parser.add_argument("--scope", default="global")
    parser.add_argument("--importance", type=float, default=0.5)
    parser.add_argument("--tags", default=None)
    parser.add_argument("--data", default=None)
    parser.add_argument("--source", default="manual")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--min-importance", type=float, default=0.0)
    parser.add_argument("--entity-id")
    parser.add_argument("--query")
    parser.add_argument("--path", help="Project path for ingest command")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be stored without writing")

    args = parser.parse_args()
    db_path = get_db_path(args.db_dir)
    store = MemoryStore(db_path)

    if args.command == "store":
        tags = json.loads(args.tags) if args.tags else []
        data = json.loads(args.data) if args.data else {}
        eid = store.store(
            type=args.type, name=args.name, text=args.text,
            category=args.category, scope=args.scope,
            importance=args.importance, tags=tags, data=data, source=args.source,
        )
        print(f"Stored {args.type}: {eid}")

    elif args.command == "get":
        if not args.entity_id:
            print("Error: --entity-id is required"); sys.exit(1)
        e = store.get(args.entity_id)
        if not e:
            print("Entity not found."); return
        print(f"ID:   {e['id']}")
        print(f"Type: {e['type']}")
        print(f"Name: {e['name']}")
        print(f"Text: {e['text']}")
        print(f"Cat:  {e['category']}")
        print(f"Scope: {e['scope']}")
        print(f"Imp:  {e['importance']}")
        print(f"Tags: {json.dumps(e['tags'])}")
        print(f"Data: {json.dumps(e['data'], indent=2)}")
        print(f"Src:  {e['source']}")
        print(f"Created: {e['created_at']}")
        print(f"Updated: {e['updated_at']}")

    elif args.command == "recall":
        results = store.recall(
            query=args.text, type=args.type, scope=args.scope,
            category=args.category, limit=args.limit,
            min_importance=args.min_importance,
        )
        if not results:
            print("No results found."); return
        print(f"Found {len(results)} result(s):\n")
        for i, r in enumerate(results, 1):
            name_part = f" [{r['name']}]" if r['name'] else ""
            print(f"{i}. ({r['type']}){name_part} {r['text'][:120]}")
            print(f"   Scope: {r['scope']} | Cat: {r['category']} | Imp: {r['importance']}")
            if r['tags']:
                print(f"   Tags: {', '.join(r['tags'])}")
            p = r.get("data", {}).get("path", "") if isinstance(r.get("data"), dict) else ""
            if p:
                exists = os.path.isdir(p) or os.path.isfile(p)
                print(f"   Path: {p}{'  ⚠ NOT FOUND' if not exists else ''}")
            print()

    elif args.command == "list":
        results = store.list_entities(
            type=args.type, scope=args.scope, category=args.category, limit=args.limit,
        )
        if not results:
            print(f"No {args.type or 'entities'} found."); return
        print(f"Total: {len(results)} {args.type or 'entities'}:\n")
        for i, r in enumerate(results, 1):
            preview = r["text"][:80] + "..." if len(r["text"]) > 80 else r["text"]
            name_part = f" [{r['name']}]" if r['name'] else ""
            print(f"{i}. ({r['type']}){name_part} {preview}")
            print(f"   ID: {r['id']} | Scope: {r['scope']} | Imp: {r['importance']}")

    elif args.command == "update":
        if not args.entity_id:
            print("Error: --entity-id is required"); sys.exit(1)
        tags = json.loads(args.tags) if args.tags else None
        data = json.loads(args.data) if args.data else None
        success = store.update(
            args.entity_id, name=args.name or None, text=args.text or None,
            category=args.category, importance=args.importance,
            scope=args.scope, tags=tags, data=data,
        )
        print("Updated." if success else "Not found.")

    elif args.command == "forget":
        deleted = store.forget(
            entity_id=args.entity_id, query=args.query,
            scope=args.scope, type=args.type,
        )
        print(f"Deleted {deleted}.")

    elif args.command == "stats":
        s = store.stats()
        print(f"Memory Statistics\n{'='*17}")
        print(f"Total: {s['total']}\n")
        print("By type:")
        for k, v in sorted(s['by_type'].items()):
            print(f"  {k}: {v}")
        print("\nBy category:")
        for k, v in sorted(s['by_category'].items()):
            print(f"  {k}: {v}")
        print("\nBy scope:")
        for k, v in sorted(s['by_scope'].items()):
            print(f"  {k}: {v}")
        print(f"\nRange: {s['oldest_timestamp'] or 'N/A'} to {s['newest_timestamp'] or 'N/A'}")

    elif args.command == "verify-paths":
        verify_paths(store)
    elif args.command == "ingest":
        ingest_project(store, args)
    elif args.command == "import":
        import_json(store, args)


def verify_paths(store):
    all_entities = store.list_entities(limit=9999)
    total = 0
    stale = 0
    fixed = 0
    for e in all_entities:
        data = e.get("data", {})
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                continue
        p = data.get("path", "") if isinstance(data, dict) else ""
        if not p:
            continue
        total += 1
        resolved = Path(p).resolve()
        if resolved.is_dir() or resolved.is_file():
            continue
        stale += 1
        print(f"  ⚠ Stale path: {e['name']} ({e['type']}) -> {p}")
        for candidate in [Path.cwd(), Path.cwd().parent, Path.home()]:
            rel = Path(p)
            if rel.is_absolute():
                continue
            guess = candidate / rel
            if guess.exists():
                store.update(e["id"], data={**data, "path": str(guess.resolve())})
                print(f"    → Updated to: {guess.resolve()}")
                fixed += 1
                break
    print(f"\nPaths checked: {total}, stale: {stale}, auto-fixed: {fixed}")


def import_json(store, args):
    path = args.path or args.text
    if not path:
        print("Error: provide a JSON file path"); sys.exit(1)
    src = Path(path)
    if not src.is_file():
        print(f"Error: not a file: {src}"); sys.exit(1)
    data = json.loads(src.read_text(encoding="utf-8"))
    data = data if isinstance(data, list) else [data]
    count = 0
    for item in data:
        if not isinstance(item, dict) or "type" not in item:
            continue
        item.setdefault("name", "")
        item.setdefault("text", "")
        item.setdefault("category", "general")
        item.setdefault("scope", "global")
        item.setdefault("importance", 0.5)
        item.setdefault("tags", [])
        item.setdefault("data", {})
        store.store(
            type=item["type"], name=item["name"], text=item["text"],
            category=item["category"], scope=item["scope"],
            importance=item["importance"], tags=item["tags"],
            data=item["data"], source=item.get("source", "import"),
        )
        count += 1
    print(f"Imported {count} entities from {src.name}")


def ingest_project(store, args):
    path = args.path or args.text
    if not path:
        print("Error: provide a project path as argument or --path")
        sys.exit(1)
    root = Path(path).resolve()
    if not root.is_dir():
        print(f"Error: not a directory: {root}")
        sys.exit(1)

    dry = args.dry_run
    project_name = root.name
    store_type = lambda: None if dry else None  # skip check in dry mode

    print(f"Ingesting project: {project_name} ({root})")

    # Read key files if they exist
    readme = read_file(root / "README.md")
    pubspec = read_file(root / "pubspec.yaml")
    package = read_file(root / "package.json")
    cargo = read_file(root / "Cargo.toml")

    # Determine project type
    ptype = "project"
    if pubspec:
        ptype = "flutter"
    elif cargo:
        ptype = "rust"
    elif package:
        ptype = "node"
    tags = [ptype, "project"]

    desc_lines = []
    if readme:
        for line in readme.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                desc_lines.append(stripped)
    description = " ".join(desc_lines[:5]) if desc_lines else f"Project at {root}"

    if not dry:
        existing = store.list_entities(type="project")
        for e in existing:
            if e["name"] == project_name:
                store.update(e["id"], text=description, tags=tags,
                             data={"readme": readme, "path": str(root)})
                print(f"  Updated project: {project_name}")
                break
        else:
            eid = store.store(type="project", name=project_name, text=description,
                              category="app", tags=tags,
                              data={"readme": readme or "", "path": str(root)})
            print(f"  Stored project: {project_name} ({eid})")
    else:
        print(f"  Would store project: {project_name}")

    # Ingest docs
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for f in sorted(docs_dir.iterdir()):
            if f.suffix in (".md", ".txt", ".rst"):
                content = f.read_text(encoding="utf-8")
                name = f.stem.replace("-", " ").replace("_", " ").title()
                first_line = content.splitlines()[0].lstrip("# ").strip() if content.strip() else name
                if not dry:
                    store.store(type="config" if "arch" in f.stem.lower() or "rout" in f.stem.lower() else "memory",
                                name=name, text=first_line[:500],
                                category="docs", tags=[ptype, "docs", f.stem],
                                data={"path": str(f), "content": content})
                print(f"  {'Would store' if dry else 'Stored'} doc: {f.name}")

    # Ingest source files
    for ext, cat in [(".dart", "dart"), (".rs", "rust"), (".py", "python"),
                     (".ts", "typescript"), (".js", "javascript"), (".go", "go")]:
        for f in sorted(root.rglob(f"*{ext}")):
            if "node_modules" in str(f) or ".dart_tool" in str(f) or ".git" in str(f) or "build" in str(f):
                continue
            rel = f.relative_to(root)
            code = f.read_text(encoding="utf-8")
            first_line = code.splitlines()[0].strip() if code.strip() else ""
            desc = first_line.lstrip("#// ").strip() if first_line.startswith(("#", "//")) else str(rel)
            if not dry:
                store.store(type="memory", name=str(rel), text=desc[:500],
                            category="code", tags=[ptype, cat],
                            data={"path": str(rel), "code": code})
            print(f"  {'Would store' if dry else 'Stored'} {cat}: {rel}")

    print(f"\n{'Dry run' if dry else 'Done'} — use `opencode-memory-store recall <query>` to find context")


def read_file(path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


if __name__ == "__main__":
    main()
