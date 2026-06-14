import sys, json, argparse
from .store import MemoryStore, get_db_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["store", "get", "recall", "list", "update", "forget", "stats"])
    parser.add_argument("text", nargs="?", default="")
    parser.add_argument("--db-dir")
    parser.add_argument("--type", default=None, choices=["memory", "project", "person", "skill", "session", "config"])
    parser.add_argument("--name", default="")
    parser.add_argument("--category", default=None)
    parser.add_argument("--scope", default="admin:global")
    parser.add_argument("--importance", type=float, default=0.5)
    parser.add_argument("--tags", default=None)
    parser.add_argument("--data", default=None)
    parser.add_argument("--source", default="manual")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--min-importance", type=float, default=0.0)
    parser.add_argument("--entity-id")
    parser.add_argument("--query")

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


if __name__ == "__main__":
    main()
