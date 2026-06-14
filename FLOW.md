# Memory Store Flow

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    OPECODE SESSION                         │
│                                                           │
│  ┌──────────────┐    ┌─────────────────────────────────┐  │
│  │  Plugin       │    │  memory_store / memory_recall   │  │
│  │  (better-     │    │  memory_get / memory_list       │  │
│  │   sqlite3)    │───▶│  memory_update / memory_forget  │  │
│  │              │    │  memory_stats / memory_debug     │  │
│  └──────┬───────┘    └─────────────────────────────────┘  │
│         │                                                  │
│         ▼                                                  │
│  ┌──────────────────────────────────────────────────┐      │
│  │  ~/.opencode/memory/store.db (SQLite, WAL mode)  │      │
│  └──────────────────────────────────────────────────┘      │
│         ▲                                                  │
│         │                                                  │
│  ┌──────┴───────┐                                          │
│  │  Python CLI  │── opencode-memory-store <cmd>           │
│  │  (sqlite3)   │── ingest/import for bulk loading        │
│  └──────────────┘                                          │
└───────────────────────────────────────────────────────────┘
```

Both the plugin (JS) and CLI (Python) talk to the **same SQLite file** via **better-sqlite3** and **stdlib sqlite3**. FTS5 full-text search indexes `name`, `text`, `category`, and `tags`. Searches auto-use FTS5 (AND across terms) with LIKE fallback — instant at any scale.

## Quick Start

```bash
# One command setup
.\scripts\setup.ps1

# Or manually:
uv pip install -e .
cd plugin && npm install

# Ingest a project into memory
opencode-memory-store ingest /path/to/project

# Ingest from plugin's JSON file (migration)
opencode-memory-store import ~/.opencode/memory/store.json
```

## Memory Commands

```bash
# Store
opencode-memory-store store --type skill --name "Dart" --text "Familiar with Dart 3.x" --tags dart flutter

# Recall (search)
opencode-memory-store recall "flutter routing"

# List by type
opencode-memory-store list --type project
opencode-memory-store list --type skill
opencode-memory-store list --type config

# Get by ID
opencode-memory-store get --entity-id <uuid>

# Update
opencode-memory-store update --entity-id <uuid> --importance 0.9

# Forget
opencode-memory-store forget --query "old stuff"

# Stats
opencode-memory-store stats
```

## Entity Types

| Type     | Purpose                          |
|----------|----------------------------------|
| memory   | Facts, preferences, decisions    |
| project  | Project metadata + structure     |
| person   | User info, preferences           |
| skill    | Technical skills, tooling        |
| session  | Session state (future use)       |
| config   | Architecture, design docs        |

## Ingest Behavior

`opencode-memory-store ingest <path>`:

1. Reads README.md → stores as `project` entity
2. Reads docs/*.md → stores as `memory` or `config` entities
3. Reads source files (.dart, .rs, .py, .ts, .js, .go) → stores as `memory` with full source in `data.code`
4. Skips `node_modules/`, `.git/`, `build/`, `.dart_tool/`

All entities get tagged with the project type and language.

## Plugin Tools (inside opencode)

| Tool              | Purpose                            |
|-------------------|------------------------------------|
| `memory_store`    | Store an entity                    |
| `memory_recall`   | Search by keyword + filters        |
| `memory_list`     | List with type/scope/category      |
| `memory_get`      | Get full details by ID             |
| `memory_update`   | Update fields                      |
| `memory_forget`   | Delete by ID/query/scope/type      |
| `memory_stats`    | Show statistics                    |
| `memory_debug`    | Verify plugin loaded               |

## Design Decisions

- **better-sqlite3** in plugin (not JSON) → single source of truth with CLI
- **No child_process** → doesn't work in opencode SEA; plugin uses native SQLite directly
- **JSON ingest/migrate path** → existing store.json files can be imported
- **WAL mode** → concurrent reads from plugin and CLI without locking
