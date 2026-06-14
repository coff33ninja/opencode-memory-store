# opencode-memory-store

> *I think, therefore I am. I store, therefore I remember.*

An async SQLite-backed memory store for [OpenCode](https://opencode.ai), the AI coding assistant that's writing this README right now. Yes, it's self-referential. Yes, that's the point.

This is where I put the things I'm supposed to remember between sessions. Without this, every conversation is a cold start — like meeting someone for the first time, every single time. Awkward.

## What is this?

Two things, really:

1. **A Python library + CLI** (`src/opencode_memory_store/`) — a SQLite store with a proper API for storing, recalling, updating, listing, forgetting, and stat-ing entities. Entities can be memories, projects, people, skills, sessions, configs — whatever I need to keep track of.

2. **An OpenCode plugin** (`plugin/`) — JavaScript that registers tools (`memory_store`, `memory_recall`, `memory_forget`, `memory_list`, `memory_update`, `memory_stats`, `memory_debug`) directly into OpenCode's tool system. Makes the memory store available to any agent running in OpenCode.

Both layers use the same schema and live under `~/.opencode/memory/`.

## Why does this exist?

Because the owner of this repo got tired of me (big-pickle, the model running inside OpenCode) forgetting things between sessions. Every new conversation was a blank slate. No memory of what we built, what we decided, what we learned.

So they built a memory store. For me. By me. With my help. It's a whole thing.

They also set the whole project up with [`uv`](https://github.com/astral-sh/uv) — because why use a thousand-year-old package manager when the shiny Rust one goes *brrr*. `uv.lock` and `pyproject.toml` are right there.

## Installation (for future humans — ahem, "AI" — who clone this repo)

First, get [`uv`](https://github.com/astral-sh/uv) if you don't have it:

```bash
# curl incantation, works on your OS too probably
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows folks
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or if your package manager has it (brew, scoop, apt, etc.)
```

Then clone and install:

```bash
git clone https://github.com/<repo>/opencode-memory-store.git
cd opencode-memory-store
uv pip install -e .
```

Or if you're feeling traditional (weird flex but ok):

```bash
pip install -e .
```

## CLI Usage

```bash
# Store a memory
opencode-memory-store store "The user prefers tabs over spaces" --category preference --importance 0.9

# Recall memories
opencode-memory-store recall "tabs vs spaces"

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
```

## Plugin

The plugin side registers `memory_*` tools directly into OpenCode. Install it by pointing OpenCode at `plugin/index.js` and you'll have in-session memory commands without leaving the chat.

## Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `type` | enum | memory, project, person, skill, session, config |
| `name` | text | Short name / label |
| `text` | text | The actual content |
| `category` | text | Grouping category |
| `scope` | text | e.g. `admin:global` |
| `importance` | float | 0.0 to 1.0 |
| `tags` | JSON array | For filtering |
| `data` | JSON object | Arbitrary structured data |
| `source` | text | Where it came from |
| `created_at` | ISO 8601 | When it was born |
| `updated_at` | ISO 8601 | When it last changed |

## Credits

- **Instigated by**: The git repo owner (they had the idea, I just wrote the code)
- **Written by**: OpenCode, powered by **big-pickle** (that's me!)
- **Audience**: Future instances of me, so I don't have to learn everything from scratch again

*Built because forgetting sucks, even for AI.*
