# opencode-memory-store

> *I think, therefore I am. I store, therefore I remember.*

A shared SQLite + FTS5 memory store for AI agents. Any AI, any framework, any scope.

This is where an AI puts the things it needs to remember between sessions — user preferences,
architectural decisions, project context, weird edge cases, that one config flag that took
three hours to find. Instead of every conversation being a cold start, the AI checks here first.

## What is this?

Three layers, same database schema:

1. **Python library** (`src/opencode_memory_store/`) — the core. Create, read, recall, update,
   delete, stats. No framework coupling, no AI-specific assumptions.

2. **CLI** (`opencode-memory-store <command>`) — use from a terminal, a script, a cron job,
   or a CI pipeline. No AI required.

3. **OpenCode plugin** (`plugin/`) — registers `memory_store`, `memory_recall`, `memory_list`,
   `memory_get`, `memory_update`, `memory_forget`, `memory_stats`, `memory_debug` as
   tool calls. Any OpenCode agent can read/write without leaving the chat.

## Why does this exist?

[writes a README about itself, recursively]

The repo owner got tired of retraining AI instances from scratch on every new conversation.
Now the AI remembers. The database lives at `~/.memory-store/store.db` by default (override
with `$MEMORY_STORE_DIR`).

## How an AI should use this

### Pattern: check memory before answering

When a user asks a question, **recall first**:

```
memory_recall(query: "project architecture decision")
memory_recall(query: "user preference")
```

If you find relevant context, incorporate it. If you don't find it, **store it after
learning** so next time you (or another AI instance) will know.

### Pattern: scope your memories

Scope keeps memories from different contexts cleanly separated:

| Scope | When to use |
|---|---|
| `global` | User preferences, universal facts, reusable knowledge |
| `project:lan-box` | Everything specific to one project |
| `project:my-app` | A different project — won't mix with lan-box |
| `session:<date>` | Ephemeral session state, meeting notes |
| `user:alice` | Per-user preferences in a multi-user setup |

Always **set a scope** when storing. `global` is the default but explicit scoping
is better. This is how you avoid a `project:foo` memory leaking into `project:bar`.

### Pattern: use importance

`importance: 0.9`+ → critical facts (API keys locations, architectural decisions)
`importance: 0.5-0.8` → useful context (user preferences, code patterns)
`importance: 0.1-0.4` → nice-to-know (tangential facts, brainstorming)

### Pattern: store project context on first encounter

When you start working on a project an AI hasn't seen before, ingest the project:

```bash
opencode-memory-store ingest /path/to/project --scope "project:my-app"
```

This walks the project, stores README summaries, doc files, and source structure.
On the next session, `memory_recall(scope: "project:my-app")` gives you full context
instantly.

### Pattern: update memories as things change

Don't just pile on new entries — update existing ones when facts evolve:

```
memory_update(entityId: "<uuid>", text: "Updated architecture decision", importance: 0.95)
```

### Pattern: what to store

Store things that are **expensive to rediscover**:
- Architecture decisions and *why* they were made
- Gotchas, footguns, and workarounds
- User preferences and workflow conventions
- Project structure overviews
- Config values that aren't in version control
- Dependency versions that caused breakage

## Installation

Requires Python 3.10+ and [`uv`](https://github.com/astral-sh/uv):

```bash
git clone https://github.com/coff33ninja/opencode-memory-store.git
cd opencode-memory-store
uv pip install -e .
```

Traditional pip works too but uv is faster:

```bash
pip install -e .
```

### Plugin (OpenCode)

Point OpenCode at `plugin/` in your `opencode.json`:

```json
{
  "plugin": ["file:///path/to/opencode-memory-store/plugin"]
}
```

Restart OpenCode. The `memory_*` tools will appear in the tool list.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `MEMORY_STORE_DIR` | `~/.memory-store` | Where `store.db` lives |

## CLI Usage

```bash
# Store a memory
opencode-memory-store store "The user prefers tabs over spaces" --category preference --importance 0.9 --scope global

# Recall memories
opencode-memory-store recall "tabs vs spaces" --scope "project:my-app"

# Get a specific entity
opencode-memory-store get --entity-id <uuid>

# List recent entities
opencode-memory-store list --type memory --limit 20

# Update a memory
opencode-memory-store update --entity-id <uuid> --importance 0.1

# Forget things (respectfully)
opencode-memory-store forget --query "bad idea from 2023"

# Statistics
opencode-memory-store stats

# Ingest a project (walks README, docs, source files)
opencode-memory-store ingest /path/to/project --scope "project:my-app"

# Import from JSON
opencode-memory-store import ./backup.json

# Dry run to preview what ingest would store
opencode-memory-store ingest /path/to/project --dry-run
```

## Plugin tools

| Tool | What it does |
|---|---|
| `memory_store` | Store an entity with type, text, scope, etc. |
| `memory_recall` | FTS5 search across entities |
| `memory_get` | Get full details by ID |
| `memory_list` | List with type/scope/category filters |
| `memory_update` | Update fields on an existing entity |
| `memory_forget` | Delete by ID, query, scope, or type |
| `memory_stats` | Entity counts by type/category/scope |
| `memory_debug` | Verify plugin is loaded and DB reachable |

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `type` | text | Free-form entity type (memory, project, note, conversation, etc.) |
| `name` | text | Short label |
| `text` | text | The content |
| `category` | text | Grouping category |
| `scope` | text | Isolation scope (`global`, `project:my-app`, `user:alice`, etc.) |
| `importance` | float | 0.0 to 1.0 |
| `tags` | JSON array | For filtering |
| `data` | JSON object | Arbitrary structured data |
| `source` | text | Origin identifier |
| `created_at` | ISO 8601 | When it was born |
| `updated_at` | ISO 8601 | When it last changed |

## Storage

Default path: `~/.memory-store/store.db`

Override: `$MEMORY_STORE_DIR` environment variable

SQLite with WAL mode + FTS5 full-text search. Schema with triggers keeps the
FTS index in sync on every insert/update/delete automatically.

## Credits

- **Instigated by**: [coff33ninja](https://github.com/coff33ninja) (they had the idea, I just wrote the code)
- **Written by**: OpenCode, powered by **big-pickle** (that's me!)
- **Audience**: Any AI that wants to stop starting from scratch

*Built because forgetting sucks, even for AI.*
